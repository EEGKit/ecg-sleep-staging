# Copyright (C) 2024  Adam M. Jones
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


""" This file is just for the SleepLoss class.
"""


import torch
from torch import Tensor
from torch.nn.modules.loss import _WeightedLoss


class SleepLoss(_WeightedLoss):
    """Loss function takes the product of the kappa of each stage.
    The loss value will be between 0.0 (best) and 1.0 (worst)."""

    def __init__(self, stage_count: int):
        super(SleepLoss, self).__init__()

        self.stage_count = stage_count
        self.loss_confusion: Tensor = torch.zeros(stage_count, stage_count)

    @staticmethod
    def calculate_loss(confusion: Tensor, stage_count: int) -> Tensor:
        """static method for just calculating the loss

        broken out so that the function can be called with other confusion matrices"""

        # sanity checks
        assert stage_count >= 2
        assert confusion.size(0) == stage_count
        assert confusion.size(0) == confusion.size(1)
        assert len(torch.where(confusion < 0)[0]) == 0

        # if the confusion matrix is all zeros, return 1.0
        if confusion.sum() == 0:
            return torch.tensor(1.0)

        # normalize the confusion matrix
        confusion = confusion / confusion.sum()

        # get the sums and diagonal
        cols = confusion.sum(0)
        rows = confusion.sum(1)
        diag = confusion.diag()

        # get all stage-wise kappas
        kappas = 2 * (diag - cols * rows) / (cols + rows - 2 * cols * rows)

        # fix any NaNs (happens when pe=1, which means both raters agree but either
        # the stage of interest or the collection of other stages is empty)
        kappas[torch.isnan(kappas)] = 1

        # shift and scale the kappas from range [-1, 1] to the range [0, 1]
        kappas = (kappas + 1) / 2

        # check kappas
        assert len(torch.where(kappas < 0)[0]) == 0
        assert len(torch.where(kappas > 1)[0]) == 0

        # calculate the final loss
        final_loss = 1.0 - kappas.prod().pow(1 / stage_count)

        return final_loss

    def forward(
        self, input_stages: Tensor, target_stages: Tensor, epoch_weights: Tensor
    ) -> Tensor:
        """pytorch forward call"""

        # copy the weights across rows
        epoch_weights = epoch_weights.unsqueeze(1).repeat(1, self.stage_count)

        # multiply the input by the weights
        # this will automatically ignore bad epochs (with weight = 0)
        input_stages = input_stages * epoch_weights

        # build confusion from each target stage
        # this will automatically ignore any padded stages (with target = -1)
        overall_confusion_list: list[Tensor] = []
        for i in range(self.stage_count):
            overall_confusion_list += [
                input_stages[target_stages == i].sum(0).unsqueeze(0)
            ]
        overall_confusion = torch.cat(overall_confusion_list, 0)

        # store a copy that can be used later.
        self.loss_confusion = overall_confusion.detach().clone()

        return self.calculate_loss(overall_confusion, self.stage_count)
