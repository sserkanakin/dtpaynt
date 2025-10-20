# Dockerfile for DTPAYNT development
## Note: On multi-arch hosts (Apple Silicon / M1/M2) Docker may pull an
## image for a different platform (linux/amd64) than the host (linux/arm64).
## If you need to force a platform at build time, pass --platform (examples
## below in the README or build instructions).

FROM randriu/paynt:cav25

# Install pytest for testing
RUN pip install pytest

# ARG defines a build-time variable with a default value. It must be
# declared after the final FROM to be available to later instructions like COPY.
ARG SRC_FOLDER=synthesis-modified

# Copy BOTH synthesis directories for testing comparison
COPY ./synthesis-modified /opt/synthesis-modified
COPY ./synthesis-original /opt/synthesis-original

# Install the specified source folder as the main installation
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

RUN export GRB_LICENSE_FILE=/opt/gurobi/gurobi.lic