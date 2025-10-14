Of course. Here is a new, complete `README.md` file for your Git repository. It explains how to build the project, what was changed, and how to run the experiments.

-----

# DTPAYNT Search Algorithm Extension

This project contains a modified version of the DTPAYNT tool, originally provided as a supplement to the CAV'25 paper, "Small Decision Trees for MDPs with Deductive Synthesis".

This README provides a complete guide to building the Docker environment, understanding our algorithmic improvements, and running experiments.

-----

## 1\. Setup and Build Instructions

Follow these steps to build the Docker container. This ensures a consistent development and testing environment for everyone on the team.

### Prerequisites

  * **Docker**: Must be installed on your system.
  * **This Git Repository**: You should have this repository cloned to your local machine.

### Build the Docker Image

1.  Open a terminal or command prompt.
2.  Navigate to the root directory of this repository (the one containing the `Dockerfile`).
3.  Run the build command. This will create a Docker image named `dtpaynt-dev`.
    ```bash
    docker build -t dtpaynt-dev .
    ```

After the build process completes, the `dtpaynt-dev` image is ready to be used for running experiments.

-----

## 2\. Our Modifications: A Smarter Search Strategy

We have modified the core search strategy of the DTPAYNT algorithm to improve how it explores potential solutions.

  * **Original Algorithm**: The original implementation uses a **stack** to process families of solutions. This results in a **Depth-First Search (DFS)**, where the algorithm explores one branch of the search space as deeply as possible before backtracking.

  * **Our Improvement**: We replaced the stack with a **priority queue**. This changes the strategy to a **Best-First Search**. The algorithm now uses its internal scoring heuristic (related to the "harmonizing value") to decide which family of solutions is the most promising to explore next. This has the potential to find optimal solutions more quickly.

-----

## 3\. How to Run Experiments

Once the `dtpaynt-dev` image is built, you can run experiments. All commands should be run from a directory where you want the results to be saved.

### The Smoke Test (Quick Verification)

A "smoke test" is a quick experiment to verify that the environment is working correctly. It runs a small subset of the benchmarks and should take less than five minutes.

#### Option A: Running without Gurobi (Recommended)

This command runs the test for our modified DTPAYNT tool and skips the comparison with OMDT.

```bash
docker run -v=$(pwd)/results:/opt/cav25-experiments/results -it dtpaynt-dev ./experiments.sh --smoke-test --skip-omdt
```

  * The `-v` flag creates a `results` folder in your current directory and links it to the container. All output files will be saved there.

If the script finishes with the message **"Smoke test passed\!"**, your setup is successful. ✅

#### Option B: Running with Gurobi (Full Comparison)

To run the full smoke test, including the comparison with the OMDT tool, you need a `gurobi.lic` file.

1.  Place your `gurobi.lic` file somewhere on your computer.
2.  Run the command below, making sure to replace `/absolute/path/to/your/gurobi.lic` with the correct path to your license file:
    ```bash
    docker run -v=/absolute/path/to/your/gurobi.lic:/opt/gurobi/gurobi.lic:ro -v=$(pwd)/results:/opt/cav25-experiments/results -it dtpaynt-dev ./experiments.sh --smoke-test
    ```

### Running the Full Experiments (Optional)

To run the entire benchmark suite instead of just the smoke test, simply remove the `--smoke-test` flag from the commands above.

**Warning**: The full experiment suite can take a very long time to complete (potentially 80-100 hours on a single thread).

-----

## 4\. Accessing Results and Debugging

  * **Results**: All generated logs, `.csv` files, and figures will appear in the `results` folder on your local machine that you linked in the `docker run` command.

  * **Interactive Shell**: If you need to debug or explore the container's file system, you can start an interactive `bash` shell by running:

    ```bash
    docker run -it dtpaynt-dev bash
    ```

    Once inside, you can navigate the file system using standard Linux commands (e.g., `ls`, `cd`). Type `exit` to leave the container.