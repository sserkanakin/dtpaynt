You are absolutely right. My apologies\! The previous `README.md` was incorrect because it didn't reflect the two-folder setup we decided on. It was still based on the old single-source structure.

Let's create the correct and final `README.md` for your repository. This version explains the two-folder structure and how to use build arguments to create the separate Docker images for comparison.

-----

# DTPAYNT Search Algorithm Extension

This project contains a modified version of the DTPAYNT tool, originally provided as a supplement to the CAV'25 paper, "Small Decision Trees for MDPs with Deductive Synthesis".

This repository is structured to manage two versions of the algorithm:

1.  **The original Depth-First Search (DFS) algorithm.**
2.  **Our modified Best-First Search (BFS) algorithm using a priority queue.**

This README provides a complete guide to building the Docker environment for both versions, understanding our algorithmic improvements, and running experiments.

-----

## 1\. Setup and Build Instructions

Follow these steps to build the Docker containers for both the original and modified algorithms.

### Prerequisites

  * **Docker**: Must be installed on your system.
  * **This Git Repository**: You should have this repository cloned to your local machine.

### Folder Structure

This repository uses a two-folder approach to manage the different code versions. The `Dockerfile` is configured to build from either folder using a build argument. The structure is:

```
.
├── Dockerfile
├── synthesis-original/     <-- Contains the original DFS code
└── synthesis-modified/     <-- Contains our new Best-First Search code
```

### Build the Docker Images

You will build two separate Docker images, one for each version of the algorithm.

1.  Open a terminal or command prompt.

2.  Navigate to the root directory of this repository (the one containing the `Dockerfile`).

3.  **Build the image for the original algorithm**:

    ```bash
    docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original .
    ```

4.  **Build the image for our modified algorithm**:

    ```bash
    docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-dev .
    ```

After these commands complete, you will have two Docker images ready for comparison: `dtpaynt-original` and `dtpaynt-dev`.

-----

## 2\. Our Modifications: A Smarter Search Strategy

We have modified the core search strategy of the DTPAYNT algorithm to improve how it explores potential solutions.

  * **Original Algorithm (`dtpaynt-original`)**: The original implementation uses a **stack** to process families of solutions. This results in a **Depth-First Search (DFS)**, where the algorithm explores one branch of the search space as deeply as possible before backtracking.

  * **Our Improvement (`dtpaynt-dev`)**: We replaced the stack with a **priority queue**. This changes the strategy to a **Best-First Search**. The algorithm now uses its internal scoring heuristic (related to the "harmonizing value") to decide which family of solutions is the most promising to explore next. This has the potential to find optimal solutions more quickly.

-----

## 3\. How to Run Experiments for Comparison

Once both images are built, you can run experiments and save the results to different folders for a direct comparison.

### The Smoke Test (Quick Verification)

A "smoke test" is a quick experiment to verify that the environment is working correctly. It runs a small subset of the benchmarks and should take less than five minutes.

#### A. Run the Original Version (DFS)

```bash
docker run -v="$(pwd)/results_original":/opt/cav25-experiments/results -it dtpaynt-original ./experiments.sh --smoke-test --skip-omdt
```

  * Results will be saved to a new `results_original` folder in your current directory.

#### B. Run the Modified Version (Best-First Search)

```bash
docker run -v="$(pwd)/results_modified":/opt/cav25-experiments/results -it dtpaynt-dev ./experiments.sh --smoke-test --skip-omdt
```

  * Results will be saved to a new `results_modified` folder.

If both scripts finish with **"Smoke test passed\!"**, your setup is successful. ✅

### Running on a Subset of Models (Recommended for a Deeper Test)
Since the full benchmark suite takes a very long time, a good alternative is to run on a significant subset of 13 models using the `--model-subset` flag. This will provide meaningful results in a more reasonable amount of time.

#### A. Run the Original Version (Subset):

Bash

```bash
docker run -v="$(pwd)/results_original_subset":/opt/cav25-experiments/results -it dtpaynt-original ./experiments.sh --skip-omdt --model-subset
```
#### B. Run the Modified Version (Subset):

Bash

```bash
docker run -v="$(pwd)/results_modified_subset":/opt/cav25-experiments/results -it dtpaynt-dev ./experiments.sh --skip-omdt --model-subset
```

#### Running with Gurobi (Optional)
To run tests with full comparison against the OMDT tool, you need a gurobi.lic file. Make sure to use the correct image name (dtpaynt-original or dtpaynt-dev) for the version you want to test.

Bash

```bash
# Example for the modified version on the smoke test
docker run -v=/absolute/path/to/your/gurobi.lic:/opt/gurobi/gurobi.lic:ro -v="$(pwd)/results_modified":/opt/cav25-experiments/results -it dtpaynt-dev ./experiments.sh --smoke-test
```

## 4. Running Priority Search Comparison Tests

To verify and compare the performance of the original stack-based search against the new priority-queue-based search, we provide automated tests.

### Quick Test (Recommended)

Simply run the provided test script:

```bash
./run_tests_docker.sh
```

This script will:
1. Build a Docker image with both synthesis versions
2. Run comprehensive comparison tests
3. Display side-by-side performance metrics

### Manual Docker Test

If you prefer to run tests manually:

```bash
# Build the test image
docker build -t dtpaynt-better-value --build-arg SRC_FOLDER=synthesis-modified .

# Run the comparison tests
docker run --rm dtpaynt-better-value \
    bash -c "cd /opt/synthesis-modified && python tests/test_priority_search_comparison_docker.py"
```

### Local Test (Without Docker)

If you have PAYNT installed locally:

```bash
cd synthesis-modified
pytest tests/test_priority_search_comparison.py -v -s
```

### Test Output

The tests will show:
- Iteration-by-iteration priority queue processing logs
- Performance comparison tables (Time, Value, Tree Size, Iterations)
- Verification that modified algorithm ≥ original algorithm in solution quality

Example output:
```
================================================================================
COMPARISON RESULTS: Simple MDP
================================================================================
Algorithm                      Time (s)        Value           Tree Size       Iterations     
--------------------------------------------------------------------------------
Original (Stack)               0.1234          9.8765          12              45             
Modified (Priority-Q)          0.0987          9.8765          12              38             

Time improvement: +20.00%
Value improvement: +0.00%
```

## 5. Accessing Results and Debugging
Results: All generated logs, .csv files, and figures will appear in the respective results folders (e.g., results_original, results_modified_subset) on your local machine.

Interactive Shell: If you need to debug or explore a container's file system, use the appropriate image name:

Bash

### To explore the modified version's container
```bash
docker run -it dtpaynt-dev bash
```
Once inside, you can navigate the file system using standard Linux commands. Type `exit` to leave the container.