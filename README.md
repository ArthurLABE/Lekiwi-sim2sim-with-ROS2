# Lekiwi-simulation-with-ROS2

In this repository, we explain step by step how to create a dataset of simulated pick&amp;place episodes from scratch, using ROS2, Gazebo and MoveIt.

Our goal is to train our robot LeKiwi to perform tasks in the real world, without necessarily having to create a real dataset via teleoperation.

We will later be able to compare the results obtained with the simulated dataset (sim2real) and those obtained with the dataset created via teleoperation.


> [!NOTE]
> Photo coming soon <br>
<br>

> [!NOTE]
> For this version, we used a **Docker** container to run **ROS2 Humble** with **Gazebo Ignition** and **MoveIt 2** with hardware acceleration (NVIDIA GPU) enabled.
> The simplest way to replicate this work would be to proceed in the same way, but you are free to try other approaches. <br>

<br>


---

## I. Prerequisites (On the host machine)

### Docker Installation
Open a terminal on your host machine (Ubuntu) and run these commands to install Docker and grant yourself execution rights:

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER 
```
> [!WARNING]
> Restart your computer now for the addition to the `docker` group to take effect.

### Installing the NVIDIA bridge (NVIDIA Container Toolkit)
For Gazebo to function smoothly, the Docker container must have access to your NVIDIA graphics card.

```bash
curl -fsSL [https://nvidia.github.io/libnvidia-container/gpgkey](https://nvidia.github.io/libnvidia-container/gpgkey) | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L [https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list](https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list) | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

---

## II. Creating the Docker image

Navigate to your working directory containing the `lekiwi_ws` folder.

```bash
cd ~/YOUR_PATH/
```

Create a file named `Dockerfile` :
```bash
nano Dockerfile
```

Paste the following configuration there, which installs ROS 2 Humble and all the necessary packages (MoveIt, Gazebo, OpenCV):
```dockerfile
FROM osrf/ros:humble-desktop

# Updating and installing robot dependencies

RUN apt-get update && apt-get install -y \
    ros-humble-pinocchio \
    ros-humble-ign-ros2-control \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-moveit \
    ros-humble-moveit-setup-assistant \
    ros-humble-joint-state-publisher \
    ros-humble-ros-gz \
    ros-humble-ros-gz-image \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Default environment configuration
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
```

Build the Docker image (this may take a few minutes):
```bash
docker build -t lekiwi_env .
```

---

## III. Launching the environment

To launch the container, forcing GPU usage and enabling the display of 3D windows, run these commands:

```bash
# Allows Docker to display windows on the host
xhost +local:docker

# Launch the container with GPU acceleration
docker run -it --rm \
    --net=host \
    --privileged \
    --gpus all \
    --env="NVIDIA_DRIVER_CAPABILITIES=all" \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="__NV_PRIME_RENDER_OFFLOAD=1" \
    --env="__GLX_VENDOR_LIBRARY_NAME=nvidia" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$PWD/lekiwi_ws:/root/lekiwi_ws" \
    --name lekiwi_container \
    lekiwi_env bash
```

---

## IV. Compiling the Workspace (Inside the Container)

Once inside the Docker container, you need to install the latest ROS dependencies and compile the project:

```bash
cd /root/lekiwi_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

---

## V. Launching the Simulation (3-Terminal Architecture)

The simulation relies on 3 components that must run in parallel. You will need to open **3 separate terminals** inside the container.

To open a new terminal in the container from your host machine, type:

```bash
docker exec -it lekiwi_container bash
source /root/lekiwi_ws/install/setup.bash
```

* **Terminal 1: The World (Gazebo & Controllers)**
  ```bash
  ros2 launch lekiwi_gazebo sim.launch.py
  ```

* **Terminal 2: The Brain (MoveIt 2 IK Solver)**
  ```bash
  ros2 launch lekiwi_moveit_config move_group.launch.py use_sim_time:=true
  ```

* **Terminal 3: The Mission (Automated Python Script)**
  ```bash
  ros2 run lekiwi_application mission
  ```

---

## VI. Useful Commands & Debugging

If you want to test the actuators individually or view the sensors, use these commands (in a terminal within the sourced container):

**Enable onboard cameras:**
```bash
ros2 run rqt_image_view rqt_image_view
```

**Test the omnidirectional base:**
```bash
# Move Forward (Repeated at 10Hz)
ros2 topic pub -r 10 /omni_drive_controller/commands std_msgs/msg/Float64MultiArray "{data: [5.0, 5.0, 5.0]}"

# Stop (Once)
ros2 topic pub --once /omni_drive_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.0, 0.0, 0.0]}"
```

**Testing the 5-axis manipulator arm live:**
```bash
ros2 topic pub --once /arm_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{joint_names: ['STS3215_03a-v1_Revolute-45', 'STS3215_03a-v1-1_Revolute-49', 'STS3215_03a-v1-2_Revolute-51', 'STS3215_03a-v1-3_Revolute-53', 'STS3215_03a_Wrist_Roll-v1_Revolute-55'], points: [{positions: [0.0, -1.57, 1.57, 0.0, 0.0], time_from_start: {sec: 3, nanosec: 0}}]}"

```

**Test the 5-axis manipulator arm live (Graphical Interface):**
*(This is the recommended method for debugging joint limits and controller status).*

If the `rqt_joint_trajectory_controller` plugin is not found initially, force ROS 2 to discover it by running:
```bash
ros2 run rqt_gui rqt_gui --force-discover

Once the blank GUI opens, here are the steps to follow to load the controller:

- In the top-left menu, click on Plugins.

- Navigate to Robot Tools > Joint Trajectory Controller.

In the new panel that appears, configure the two dropdown menus:

- Controller Manager: Select /controller_manager.

- Controller: Select arm_controller.

The 5 sliders for your arm's joints will appear. You can now move the sliders with the mouse to control the robot live in Gazebo.











    
