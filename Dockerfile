# Dockerfile for DTPAYNT development
# ARG defines a build-time variable with a default value
ARG SRC_FOLDER=synthesis 

FROM randriu/paynt:cav25

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

RUN export GRB_LICENSE_FILE=/opt/gurobi/gurobi.lic