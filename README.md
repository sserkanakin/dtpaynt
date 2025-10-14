# Small Decision Trees for MDPs with Deductive Synthesis

This artifact supplements CAV'25 paper *Small Decision Trees for MDPs with Deductive Synthesis*.


Contents of the artifact:
- `dtpaynt.tar`: the Docker image containing the tools and benchmarks discussed in the paper, as well as scripts for their automated evaluation
- `Dockerfile`: the dockerfile used to create `dtpaynt.tar`
- `LICENSE`: the license file
- `README.md`: this readme

The first part of this README describes how to use the artifact to replicate results presented in the paper. The latter part presents the tools, their installation and their usage outside the scope of this artifact, as well as a description of the benchmarks used for experimental evaluation .

[toc]

---

## Reproducing the experiments

### Running without OMDT

In Q1 of experimental evaluation we compare our approach dtPaynt with OMDT which uses Gurobi as an LP solver. If you cannot acquire Gurobi license skip the next paragraph and ignore all of the instructions connected to Gurobi. We equipped the `experiments.sh` script with the option `--skip-omdt` to skip comparison to OMDT, and if you still wish to have the figures for Q1 generated you can use our provided logs for OMDT as a replacement, keeping in mind that this option might yield some discreprencies in the final results.

### Acquiring Gurobi license

In the experiments, we compare our approach with the tool OMDT, which is a baseline for our experiment. The provided docker image comes with a pre-installed version of OMDT. However, OMDT uses Gurobi which requires a license, and to run it within the Docker environment, Gurobi provides a dedicated Web License Service (WLS). This service can be accessed via a *free* academic license. All you need to do is to register at https://www.gurobi.com/, request an Academic WLS License (Licenses->Request->Academic WLS License->Generate Now!->Confirm Request->Open in License Manager), and download the license file `gurobi.lic`. The process should not take more than five minutes. For more information about Gurobi Web License Service, visit https://license.gurobi.com/manager/doc/overview/. 


### Using the Docker and quick start

Load the image `dtpaynt.tar` into your Docker environment using:
```
docker load -i dtpaynt.tar
```

If you get a permission error, make sure to precede docker commands with `sudo` to acquire root privileges. Upon loading the image, you can run the container as follows:

```
docker run -v=/absolute/path/to/gurobi.lic:/opt/gurobi/gurobi.lic:ro -v=$(pwd)/results:/opt/cav25-experiments/results -it dtpaynt
```

`-v=/absolute/path/to/gurobi.lic:/opt/gurobi/gurobi.lic:ro` mounts your Gurobi license and `-v=results:/opt/cav25-experiments/results` mounts your local folder `$(pwd)/results`, where the automated scripts will store the output of the experiments -- this will allow you to inspect the generated results outside the docker environment, even after it is no longer running. Once inside the container, you can verify that the license file is mounted correctly by running

```
gurobi_cl
```

You can exit the container via `exit` or `^D`. Upon finishing your review, you can remove the image and the associated containers from the your Docker environment using:
```
docker ps -a --filter ancestor=dtpaynt --format "{{.ID}}" | xargs docker rm
docker rmi dtpaynt
```



### Smoke test

When starting the container, you will be placed in `/opt/cav25-experiments` folder which contains the script `experiments.sh`, your main entry point for the experiments. The smoke test can be initiated by running:
```
./experiments.sh --smoke-test
```

This will evaluate dtPaynt and OMDT for max depth 1 with 30 second timeouts and dtControl with default settings on six selected benchmarks. The script will generate log files for these experiments and three .csv files in the `results/logs` folder. If you get the message "Smoke test passed!", you are all set. You can still double check the .csv files generated in `results/logs`, they should not contain any N\A values. The smoke test should not take more than five minutes.

Note that if you don't have the Gurobi license you can run:
```
./experiments.sh --smoke-test --skip-omdt
```

This will verify that at least dtPaynt and dtControl work as intended.


### What can be replicated

The results from Q1, Q2 sections of the experimental evaluation and results from appendix can be replicated via the main `./experiments.sh` script.
More specifically, the script generates Fig. 2 from section Q1, Fig. 3 from section Q2, and Tab. 2, Fig. 4, Fig. 5 from the Appendix. Note that Figures 3 and 5 will have the dtControl "depth" labels missing as dtControl does not export these values and they were obtained manually for the paper. The depths of dtControl trees can be found in the provided `original-logs/final-merge.csv` in the column `dtcontrol depth`.

The result generation for Q3 and Q4 have never been fully automated, unfortunately. This includes Table 1. However, for these results we provide two scripts, `./experiments-q3.sh` and `./experiments-q4.sh` that produce log files associated with the experiments. Interpreting these log files is explained in the latter part of this README. Since the process is not automated, we do not explicitly ask the reviewers to inspect these log files, nonetheless, they are welcome to do so.

### Executing the evaluating script

Running the benchmark script `./experiments.sh` will generate all of the log files for dtPaynt, OMDT and dtControl for all of the 21 models in our benchmark set, and then generate all of the figures from the paper. Here is a list of options for the `./experiments.sh` script:

- `--smoke-test` - runs the smoke test.
- `--no-threads X` - runs the experiments using X parallel cores. Note at least 16GB of RAM per core is recommended. Default value is 2.
- `--model-subset` - runs the experiments for a subset of models (13 out of 21 models).
- `--skip-omdt` - skips the evaluation of the OMDT tool.
- `--overwrite` - overwrites already created log files.
- `--provided-logs` - generates the figures from the logs in `original-logs` which were used to generate the figures in the paper.
- `--generate-only` - only runs the generation of results and skips all the evaluation steps. Note this should only be used when log files for a substantial part of the benchmark set have been created already. 

The generated log files are stored in `results/logs` folder and the final figures and tables are generated in `results/generated-results` folder. Recall that the `results` folder is mounted to your host system, so you can inspect them outside the Docker environment.

When executing the script repeatedly, it detects whether the log files already exist, so you *can abort without loss of progress*. To re-run the experiments completely, simply delete the corresponding log files or use option `--overwrite` to force the overwrite.

In case the script encounters an error, it generates an error message and proceeds with the evaluation. As a result, the generated figures might be missing some data. You can check the log files to see which experiments failed, remove the corresponding log files and re-run the script if you wish so.

Given the nature of the experiments, their outcome heavily depends on the timing, so the produced tables and figures might be different, although the underlying qualitative comparison of the approaches should be preserved. The original results were obtained on a PC equipped with AMD EPYC 9124 16-Core Processor (each experiment uses single core) and 360GB of RAM. The experiments can be run on much more modestly equiped PCs/laptops, although it might happen that some more demanding experiments will run out of memory or simply lead to worse results.

The original log files that were used when preparing the submission can be found in `original-logs`. If you wish to generate results from these log files use the option `--provided-logs`.


#### Tackling the long runtime

The runtime of the whole experiments depends on the number of threads you can use which can be adjusted in the file `./experiments.sh` by using the option `--no-threads X` or changing the value of `thread_count` (default 2). Note that you ideally need at least 16GB of RAM per thread. The whole benchmark will take 21 (models) * 8 (depths) * 20 (minutes) * 2 (tools: OMDT + dtPaynt) + few minutes for dtControl = ~80-100 hours on a single thread.

To help with this potentially very long runtime we introduce the following options:

- `--model-subset` - run only subset of models (13 models), this removes some problematic models where OMDT requires a lot of memory. Using this option should halve the overall runtime while still somewhat capturing the nature of the experiments.
- `--skip-omdt` - will skip OMDT evaluation, you can copy the OMDT logs from `original-logs` folder using `cp -r ./original-logs/omdt-cav-final ./results/logs/`. If you use this option please mind the possible discrepency in the values and runtimes since the comparison will be on runs from different machines.
- `--generate-only` - will use the current log files from `results/logs` folder to try and generate the results without running any experiment (besides dtControl ones if the dtControl csv file with results is missing). This can be useful when some of the log files are missing due to high memory requirements for example but you would like to generate the results for the log files you have without reruning anyhting.


### What to look for in the Q3 and Q4 experiments

When the `./experiments-q3.sh` script finishes, it will create a csv file in `results/logs/paynt-q3-final.csv`. This csv file includes dtPaynt results for 4 different depth on each of the 5 considered models. For each model and each depth you can look at the values in column `best relative`, which will be value between 0 and 1. The closer they are to 1 (1 corresponds to the value of the optimal policy) the better the produced DT at that depth is. In this experiment, the point was to showcase that there are big MDPs where small depth DTs suffice and dtPaynt is able to find them, therefore seeing values that get close to one in column `best relative` in this table proves this point. The values for dtControl are not reproduced due to the fact that huge scheduler files were needed in these experiments.

The `./experiments-q4.sh` script will create log files for the two models mentioned in Q4 and save them to the `results/logs/paynt-cav-q4/` folder. You can view these logs and search for the line `initial external tree has depth X and Y nodes` which says the initial DT size which was produced by dtControl and than compare it with the line `final tree has value X with depth Y and Z nodes` which says the size of the DT after reduction using dtPAYNT. This experiment was to showcase that dtPaynt can be used as a tool for reducing size of big DTs, therefore comparison of these two values should indicate that dtPaynt is capable of reducing the size significantly. You can also check the line `the synthesized tree has relative value: X` to see the value of the reduced DT. This value should stay above 0.99 which means that it is within 1% of the value of the optimal policy.

---

## Artifact dependencies


dtPaynt is implemented as an extension of the tool [Paynt](https://github.com/randriu/synthesis), which is built on top of [Storm](https://github.com/moves-rwth/storm) and [Stormpy](https://github.com/moves-rwth/stormpy). Below we document for each tool, including [OMDT](https://github.com/tudelft-cda-lab/OMDT) and [dtControl](https://gitlab.com/live-lab/software/dtcontrol), specific versions used for this submissions. Note that all of the tools considered are open-source. All depedencies are up-to-date at the moment of writing this README.
 
- **dtPaynt**
    - latest version: https://github.com/randriu/synthesis/tree/ab0c7d1548286a5af1524a034cd06f75550163e7
    - uses Stormpy (see https://github.com/moves-rwth/stormpy/tree/6ada9367411d2335490ec464d8aec4045a7c37ed)
    - uses Storm (see https://github.com/moves-rwth/storm/tree/aaa39c33afa513116600162fd29c713465518f23) with a patch enabling model checking wrt. discounted-reward specifications (see https://github.com/AlexBork/storm/tree/8109826f721341fcaf71d0a7ca8bf8d7fd005963)
- **OMDT**
    - latest version (includes parsing for .drn models): https://github.com/TheGreatfpmK/OMDT/tree/4c3f5f629b096a8b28d94e91b96aab330757314d
- **dtControl**
    - latest version: https://gitlab.com/live-lab/software/dtcontrol/-/tree/d53387a4e31efc2fcee280d06e61f511d7fe6255

The `Dockerfile` included in this artifact was used to create the Docker image `dtpaynt.tar`. To learn about installing any of these tools outiside the Docker environment, please visit the linked documentation above.


## Using the tools outside the scope of the artifact

We provide a small overview of how to use the tools outside of the benchmark script. For the full information, please visit the linked documentation.

### dtPaynt

dtPaynt is part of the tool PAYNT which is written in Python3. To run the small decision tree synthesis use:

```
python3 paynt.py path/to/model/folder --sketch model-file --props props-file --tree-enumeration --tree-depth=X --timeout Y
```

where `model-file` is the name of the model file in the model folder and `props-file` is the name of the props file in the model folder. `X` represents the maximum depth the synthesized DT should have. `Y` is the timeout in seconds. This command assumes the model folder contains both the model description and a specification. For more information about the settings of PAYNT, visit https://github.com/randriu/synthesis.

### OMDT

OMDT is also written in Python3. It uses the LP solver Gurobi to find small DTs. For more information on installation of OMDT follow: https://github.com/tudelft-cda-lab/OMDT. To run OMDT from https://github.com/tudelft-cda-lab/OMDT (original IJCAI'23 implementation) use:

```
python3 run.py omdt model-name --seed 0 --max_depth X --time_limit Y
```

where model-name is the name of the model, X the max depth of the DT and Y the time limit in seconds. To run OMDT from https://github.com/TheGreatfpmK/OMDT which also supports the parsing of drn format models.

```
python3 run-experiment.py omdt model-name --seed 0 --max_depth X --time_limit Y --model-file-name model-file.drn
```

where additionally model-file.drn is the name of the drn file in the given model folder.

Note that OMDT only takes MDP file as input as it assumes a discounted reward specification.


### dtControl

dtControl is also written in Python3. It is different from the other two tools on the input it expects. dtControl takes a scheduler as an input and produces a DT representing this scheduler. For more information on the installation of dtControl refer to: https://gitlab.com/live-lab/software/dtcontrol. To run dtControl use:
```
dtcontrol --input path/to/scheduler-file.storm.json -r --use-preset default
```

In our case we considered schedulers exported by the model checker Storm (https://www.stormchecker.org/). To parse the schedulers from Storm, dtControl expects they have the file extenstion `.storm.json`.

## Exporting the DTs

If you are interested in exporting the resulting DT from dtPaynt you can call PAYNT with additional option `--synthesis-export path/to/result` which then produces .dot representation of the tree together with .png file which contains visualization of the DT. 


## Parts of the source code relevant to the paper

The following are selected parts of the source code relevant to the algorithms discussed in the paper:

- `/opt/paynt/synthesizer/decision_tree.py` ([github](https://github.com/randriu/synthesis/blob/ab0c7d1548286a5af1524a034cd06f75550163e7/paynt/synthesizer/decision_tree.py)) - contains the high level logic of the algorithm, such as controlling the increasing depths or producing the output.
- `/opt/paynt/quotient/mdp.py` ([github](https://github.com/randriu/synthesis/blob/ab0c7d1548286a5af1524a034cd06f75550163e7/paynt/quotient/mdp.py)) - contains class for MdpQuotient which holds the information about state valuations of variables and holds the symbolic representation of possile DTs and also includes a class for representing DTs.
- `/opt/paynt/payntbind/src/synthesis/quotient/ColoringSmt.cpp` ([github](https://github.com/randriu/synthesis/blob/ab0c7d1548286a5af1524a034cd06f75550163e7/payntbind/src/synthesis/quotient/ColoringSmt.cpp))- module responsible for creating the SMT formulas.

## Testing the correctness of dtPaynt

To ensure the correctness of the results provided by dtPaynt, we always double check the DT we output. This double checking includes obtaining action for each state from the DT to create the induced DTMC. Then we model check the induced DTMC using the model checker Storm (https://www.stormchecker.org/) to verify the result.

## Benchmarks

Our benchmarks come from three sources:

- [OMDT benchmarks](https://github.com/tudelft-cda-lab/OMDT/tree/main/environments) from the IJCAI'23 paper. We excluded 2 models from this set as one had continuous domains and one had multiple initial states
- QComp benchmark set for MDPs (https://qcomp.org/benchmarks/). We only included models which were implemented in the [Prism language](https://www.prismmodelchecker.org/manual/ThePRISMLanguage/Introduction) as they include the state variables and valuations needed to produce DTs. We also excluded 2 models from this benchmark set as the action labels overlapped.
- We included 2 grid-world models `maze-7` and `maze-steps` which we designed ourselves based on maze models from the literature.

OMDT implementation expects discounted reward properties therefore all of the models were adjusted to support these properties for fair comparison. We also exported all of the models to the drn format (using Storm) for which we implemented a parser in the OMDT implementation.

All of the considered benchmarks can be found at `benchmarks/all`.
