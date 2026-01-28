FROM python:3.11-slim

# 1. Install System Dependencies
# We use 'libgl1' instead of 'libgl1-mesa-glx' for Debian Bookworm compatibility
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    libgl1 \
    libxi6 \
    libxrender1 \
    libxfixes3 \
    libxkbcommon0 \
    dbus-x11 \
    libsm6 \
    libxext6 \
    libegl1 \
    libopengl0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Blender 4.2 LTS
# Using the official release mirror ensures this link won't expire like daily builds
ENV BLENDER_VERSION=4.2.0
ENV BLENDER_URL=https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz

WORKDIR /tmp
RUN wget -q --show-progress ${BLENDER_URL} -O blender.tar.xz \
    && mkdir /opt/blender \
    && tar -xJf blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm blender.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

# 3. Verify Installation
RUN blender --version

# 4. Install Python Dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Application Code
COPY . .

# 6. Runtime Configuration
ENV BLENDER_PATH=/usr/local/bin/blender
ENV PYTHONUNBUFFERED=1

RUN mkdir -p runs

EXPOSE 8001

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
