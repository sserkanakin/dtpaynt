# to build, run
# docker build -t dtpaynt-dev .

FROM randriu/paynt:cav25

# Step 1: Copy our local 'synthesis' code into the image at /opt/paynt
# This overwrites the version that came with the base image.
COPY ./synthesis /opt/paynt
WORKDIR /opt/paynt

# Step 2: Re-install the paynt tool from our local code
# This ensures the system uses our version.
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
RUN apt-get install -y vim

RUN git clone https://github.com/randriu/dt-synthesis-cav-25.git cav25-experiments
WORKDIR /opt/cav25-experiments

RUN export GRB_LICENSE_FILE=/opt/gurobi/gurobi.lic