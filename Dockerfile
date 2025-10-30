# Dockerfile for DTPAYNT development
## Note: On multi-arch hosts (Apple Silicon / M1/M2) Docker may pull an
## image for a different platform (linux/amd64) than the host (linux/arm64).
## If you need to force a platform at build time, pass --platform (examples
## below in the README or build instructions).

FROM randriu/paynt:cav25

# ARG defines a build-time variable with a default value. It must be
# declared after the final FROM to be available to later instructions like COPY.
ARG SRC_FOLDER=synthesis

# Copy the specified source folder and reinstall it
COPY ./${SRC_FOLDER} /opt/paynt
WORKDIR /opt/paynt
RUN pip install .

# --- The rest is from the original Dockerfile ---
WORKDIR /opt/
RUN git clone https://gitlab.com/live-lab/software/dtcontrol.git
WORKDIR /opt/dtcontrol
RUN git checkout paynt-colab
RUN pip install .
WORKDIR /opt/
RUN git clone https://github.com/TheGreatfpmK/OMDT/

RUN pip install matplotlib gym gurobipy pydot
RUN apt-get update && apt-get install -y vim

RUN git clone https://github.com/randriu/dt-synthesis-cav-25.git cav25-experiments
WORKDIR /opt/cav25-experiments

# Copy the extended experiments script with epsilon-optimal-stop support
COPY ./${SRC_FOLDER}/experiments-dts-cav-extended.py ./experiments-dts-cav.py
# Copy the wrapper script with epsilon-optimal-stop support
COPY ./${SRC_FOLDER}/experiments-wrapper.sh ./experiments.sh
RUN chmod +x ./experiments.sh

RUN export GRB_LICENSE_FILE=/opt/gurobi/gurobi.lic