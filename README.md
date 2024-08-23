# Expert-level ECG-only sleep staging

This repository contains all the code and data used in the paper (<https://doi.org/10.1016/j.compbiomed.2024.108545>).

If you find this repository helpful, please cite the paper:

> Adam M. Jones, Laurent Itti, Bhavin R. Sheth, "Expert-level sleep staging using an electrocardiography-only feed-forward neural network," Computers in Biology and Medicine, 2024, doi: 10.1016/j.compbiomed.2024.108545

---

1. [Sleep scoring your own data](#sleep-scoring-your-own-data)
2. [Data file description](#data-file-description)
3. [Benchmark dataset](#benchmark-dataset)
4. [Loss function](#loss-function)
5. [Paper replication](#paper-replication)
6. [Requirements](#requirements)

---

## Sleep scoring your own data

To get this into the hands of others and in use as soon as possible, there is a separate folder structure just for new and future users (verses documenting what was done for the paper, below).

### ECG Equipment

Unfortunately, there are few commercial ECG recording devices on the market right now. I am only aware of two devices that could possibly work and be worn comfortably while asleep. However, I have not personally tried either yet, so I cannot vouch for them.

- [Movesense](<https://www.movesense.com/>)
    - The [sampling rates](<https://www.movesense.com/docs/esw/api_reference/>) are: 125, 128, 200, 250, 256, 500, and 512 Hz.
- [Polar H10](<https://www.polar.com/us-en/sensors/h10-heart-rate-sensor/>)
    - The [sampling rate](<https://github.com/polarofficial/polar-ble-sdk>) is: 130 Hz.

However, if you are using clinical or research ECG equipment to record ECG there are a few important details to keep in mind:

- The recording should be of Lead I (limb lead across the heart). See [ECG Lead positioning](https://litfl.com/ecg-lead-positioning/) for the proper locations of the "RA" and "LA" electrodes.
- The sampling rate should be a minimum of 125 Hz. Higher is better, with the "optimal" rate for the network's input being 256 Hz.
- The sampling resolution should be a minimum of 16 bits. Higher is better.

### Data processing

While all of the code that was used for everything described in the paper is in the `paper` folder, that code was originally designed around processing thousands of files in parallel in specific steps (which was easier to write in MATLAB at the time).
To process your own data, you can take it through that same pipeline (either a file at a time or many files simultaneously). Or, you can instead just extract your own ECG/EKG data and filter it (as described in the paper and in the `Data file description` section below).
Eventually, I will rewrite the pipeline to accommodate the processing of individual files and convert all MATLAB code to Python. This code will go in the `data_processing` folder (which currently just has a placeholder file).

#### Expectations for ECG input

If you are processing data using your own pipeline, your need to make sure that the final output (the input ECG for the network), matches the expectations listed in the paper. Specifically, the network expects the following:

1. Noise has been filtered:
    - High-pass filtered at 0.5 Hz to remove baseline wander.
    - Line noise (50/60 Hz) and any other constant-frequency noise has been removed with a notch filter(s).
2. Sampled at 256 Hz (resample **-after-** filtering).
3. The data has been scaled in the following manner:
    - The median of all data should been subtracted (such that the median = 0).
    - You have measured the min and max values for every heartbeat (**NOT** all data, just the heartbeats). And then you have scaled the data such that the 90th percentile (or greater) of the min and max lies within the range [-0.5, 0.5].
    - Movement artifacts and other noise may exceed the amplitude of most heartbeats, and it is okay if those values lie within the range of [-1, -0.5] and [0.5, 1].
    - Regardless of abnormally "tall" heartbeats or noise, all values should be clamped to [-1, 1].
4. Finally, divided/reshaped into 30-second epochs (shape: epoch_count x 7680).

When loading data, the network's code will test, by default, if any values are outside [-1, 1] and if the median ~= 0. However, it will not know if the ECG is scaled inappropriately (such that heartbeats generally exceed [-0.5, 0.5]).

The figure below should hopefully make the above ECG requirements clearer.

![Expected Network Input](docs/assets/beat_voltage_diagram.png?raw=true)


### Sleep stage scoring (primary or real-time model)

There is a folder for each model: `primary` and `real-time`. They are completely self-contained, and, as a consequence, are almost exact duplicates. However, the parameters in the `train_params.json` file are set up to sleep score on individual files right away. The code can run with or without a GPU.

To use either model, just run the following from your python environment:

```
python train.py your_datafile.h5
```

The `your_datafile.h5` can either be in the same folder, or elsewhere (as long as the complete path is provided). The code will load the appropriate model, check the file, score the sleep, and save a `results.h5` file in the same folder.

If you need any assistance, please feel free to file an issue in the repository or contact me (contact details provided in the paper). I will be happy to help you use and modify the code to work on your own data, as well as replicate anything from the paper.

#### Primary model without demographics (new)

A new primary model that does not require the subject's demographics (age and sex) is now available. The Cohen's kappa for this model on the testing set is 0.718 (which is >99% of the performance of the primary model with demographics). To clarify, this model will only need the variables `ecgs` and `midnight_offset` to perform inference.

This model was created after the paper was published, and is therefore not discussed in the paper.

### FYI: description of files inside model folders

- `adams.py` (optimizer, original source here: [zeke-xie/stable-weight-decay-regularization](<https://github.com/zeke-xie/stable-weight-decay-regularization>))
- `net_params.json` (network hyperparameters)
- `sleep_support.py` (various support functions)
- `sleepdataset.py` (dataset loader and processing)
- `sleeploss.py` (loss function)
- `sleepnet.py` (network and batch collation)
- `train_params.json` (training hyperparameters)
- `train.py` (main program)
- `[the name is unique].pt` (the weights for the model)

---

## Data file description

Each file, representing a single night of sleep (or a portion thereof) that the network code will ingest, should be provided in HDF5 files with the following `datasets` (the term HDF5 uses for variables):

If just performing inference (only scoring data, and not training), then only the first three variables are required for the loader to operate. However, all five variables are necessary if training the network.

- `ecgs`:
  - 2D array of floats (size: epoch_count x 7680)
  - Where 7680 = 30 x 256Hz.
  - Network was trained on raw ECG data that had been filtered and scaled appropriately. See **Expectations for ECG input** above.
- `demographics`:
  - 2D array of floats (size: 2 x 1):
    - 1st: sex (0=female, 1=male)
    - 2nd: age (age/100)
- `midnight_offset`:
  - A float that represents the clock time offset to the nearest midnight of when the recording began:
    - 0 = midnight
    - -1 = 24hr before midnight and 1 = 24hr after midnight
    - For example, 9pm = -0.125 and 3am = 0.125.
- `stages` (only required for training):
  - 2D array of floats (size: epoch_count x 1):
    - Stage mapping: 0=Wake, 1=N1/S1, 2=N2/S2, 3=N3/S3/S4, 4=REM.
      - It is not uncommon to find REM mapped to 5. However, the network was trained with data with both AASM and R&K scorings, so a unified "deep sleep" score was mapped to 3. And because it's inconvenient to have a gap, REM was remapped to 4.
    - All "unscored" epochs should be mapped to 0 (also see weight below).
- `weights` (only required for training):
  - 2D array of floats (size: epoch_count x 1):
    - 0 (no weight) to 1 (full weight)
    - All "unscored" epochs should be given a weight of 0.

---

## Benchmark dataset

The study included training, validating, and testing on a dataset of 4,000 recordings that were randomly sampled from five different source studies. Additionally, a held-out study was used to evaluate any study-specific learning. Although I do not have permission to share the source data, they are available at the National Sleep Research Resource (<https://sleepdata.org/>). To facilitate the creation and use of a standardized benchmark (which this field sorely needs), I have provided a listing of all of the file names so that others can train, validate, and test the exact same dataset I used.

### benchmark dataset

- `main_sets.xlsx` contains the listing for the train, validation, and testing sets
- `heldout_set.xlsx` contains the listing for the held-out study

---

## Loss function

A new Cohen's-kappa-correlated loss function was designed for this work, which is included in the self-contained model folders. However, its main repository (with looser licensing) is at (<https://github.com/adammj/loss-functions>).

---

## Paper replication

All of the code and intermediate results that were used to evaluate the final model are included here.

0. **0_data_processing**
   - Contains all of the pre-processing code that was used. As described above, this was written in MATLAB with the goal of processing thousands of files in specific steps. The files can (fairly easily) be modified to process a single file at a time. However, I am working on a streamlined Python version to future users.
1. **1_meta_analysis**
   - The inputs, R code, and output for the meta-analysis.
2. **2_intermediate_data**
   - The intermediate data that was created from the various experiments described and plotted in the paper.
3. **3_figures**
   - All of the figure files (Jupyter notebooks and one Keynote file). Each notebook will produce a PDF and PNG file for each figure.
   - The scatter plot in Figure 8 requires a large (280MB) file, `tsne_results.mat`. It was not uploaded due to GitHub limitations. Please contact me if you would like a copy of the file.

---

## Requirements

The toolbox and package requirements to run the code are as follows:

- Python
  - I've provided three different `requirements.txt` files, depending on your needs. These were created with [conda](<https://docs.anaconda.com/miniconda/miniconda-install/>), as this is the package manager I use for the more complex requirements of [PyTorch](<https://pytorch.org/get-started/locally/>). 
  - If you just want to score sleep using one of the models, then you only need to `requirements_cpu.txt` file. However, if you would like to train the model, or otherwise make use of your GPU, then use `requirements_gpu.txt`. Finally, if you want to reproduce the figures from the paper, use `requirements_paper.txt`.
- MATLAB (2023a)
  - Parallel Computing Toolbox (7.8)
  - Signal Processing Toolbox (9.2)
- R (4.3.2)
  - DescTools (0.99.54)
  - pimeta (1.1.3)
  - readxl (1.4.3)

---

Paper links:

- [Published paper](<https://doi.org/10.1016/j.compbiomed.2024.108545>)
- [Preprint version](<https://www.medrxiv.org/content/10.1101/2023.10.13.23297018v1>)
    - There were some large changes between the preprint and the final, published, version (mainly revolving around adding a large meta-analysis). However, the network and testing set results are the same.

---

Copyright (C) 2024  Adam Jones  All Rights Reserved

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
