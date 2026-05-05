# Lerobot-simulation-with-ROS2

In this repository, we explain step by step how to create a dataset of simulated pick&amp;place episodes from scratch, using ROS2 and Gazebo or RViz.

Our goal is to train our robot LeKiwi to perform tasks in the real world, without necessarily having to create a real dataset via teleoperation.

We will later be able to compare the results obtained with the simulated dataset (sim2real) and those obtained with the dataset created via teleoperation.

<img width="70%" height="618" alt="image" src="https://github.com/user-attachments/assets/e4d3b61c-f8f4-4c82-89a8-8f3b0307e686" />

<br>

> [!NOTE]
> This repository is an adaptation of https://github.com/ycheng517/lerobot-ros and https://github.com/Pavankv92/lerobot_ws. If in doubt, please consult those pages.<br>

<br>

## I- ROS2 (and others) installation


### 0. Install ROS 2 (If starting from scratch)

If you don't have ROS 2 installed on your machine, you must install ROS 2 Humble (the recommended version for this project) on Ubuntu 22.04 before running any of the following commands.

  - Official Installation Guide: https://docs.ros.org/en/humble/Installation.html
    (We recommend the "Desktop Install" to get RViz and other visualization tools by default).

Why "humble"? Simply because we did it with this version. You can try replacing each time "humble" with "jazzy" (or another one), it might work but we haven't tested it.

<br>

### 1. Source ROS 2 (ex for Humble)
    source /opt/ros/humble/setup.bash
<br>

### 2. Clone the robot workspace
    git clone https://github.com/Pavankv92/lerobot_ws.git
    cd lerobot_ws/
<br>

### 3. Install required ROS 2 dependencies
> [!TIP]
>You may need to adapt these commands to your version by replacing "humble" with "jazzy" or another one(yours).

    rosdep update
    rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
    sudo apt install ros-humble-moveit ros-humble-moveit-setup-assistant
    sudo apt install ros-humble-cv-bridge
    sudo apt install ros-humble-pinocchio
<br>

### 4. Install Python dependencies (Pinocchio and Catkin fix)

    pip install pinocchio
    sudo apt-get install python3-catkin-pkg
<br>

### 5. Build the workspace

    colcon build
<br>

<br>

## II. (OPTIONAL) 3D Model Preparation (Only if modifying XACRO)

> [!WARNING]
>If you modify the .xacro file (e.g., to add a camera or adjust the Tool Center Point), you must always compile it back into a .urdf file before launching the simulation.

Our modified urdf files are located in the attached folder, put them in the following folder : lerobot_ws/src/lerobot_description/urdf

<br>

### Replace the paths with your own absolute paths 
    xacro ~/YOUR_PATH/lerobot_ws/src/lerobot_description/urdf/so101_base.xacro > ~/YOUR_PATH/lerobot_ws/src/lerobot_description/urdf/so101_base_compiled.urdf
<br>

<br>

<br>

## III. Launching the Simulation (Standard Procedure)

To use the simulated robot, you will need 3 to 4 terminals.

 In each new terminal, navigate to **lerobot_ws** (with cd command) and execute these two commands before doing anything else:

    conda deactivate #if necessary
    source /opt/ros/humble/setup.bash
    source install/setup.bash

<br>

<br>

### Terminal 1: Launch Gazebo (The 3D Environment)

    ros2 launch lerobot_description so101_gazebo.launch.py
<br>

### Terminal 2: Launch Controllers 

    ros2 launch lerobot_controller so101_controller.launch.py
<br>

### Terminal 3: Open the Video Bridge (To receive cameras in Python)
> [!NOTE]
> We used image_bridge here as it is much more performant than parameter_bridge for 30 FPS video streams.

    ros2 run ros_gz_image image_bridge /camera_base/image_raw /camera_pince/image_raw
<br>

### Terminal 4: Run your Python Script (Dataset Generation / Inverse Kinematics)

    cd ~/YOUR_PATH/lerobot_ws/src/

    python3 dataset_generator.py
<br>

> [!NOTE]
> Camera record is by default launching "python3 dataset_generator.py" but you can disable it by launching 
> "python3 simu_sans_rec.py"
<br>

### BONUS : Visualization 
Display live camera feeds: in another **sourced** terminal (or two others for both cameras):

    ros2 run rqt_image_view rqt_image_view
<br>

<br>

## IV. Tools & Debugging

These commands are useful to manually test the robot, visualize data with RViz, or record actions.
<br>

### Spawn the red box manually
    ros2 run ros_gz_sim create -file ~/YOUR_PATH/lerobot_ws/src/lerobot_description/urdf/red_box.sdf -name ma_boite_rouge -x -0.2 -y 0.0 -z 0.015
<br>

### Open RViz (To see markers and the internal TF skeleton):
For the visual verification of the robot in motion :

    ros2 launch lerobot_description so101_display.launch.py

To see it mooving with the script (almost like Gazebo) : 

    ros2 launch lerobot_moveit so101_moveit.launch.py
<br>

> [!WARNING]
> RViz Troubleshooting: If RViz opens with a Frame [Base] does not exist error, go to Displays (left panel) > Global Options > Fixed Frame, and change "Base" to "World".
> If that doesn't work, close the window and try again after pressing Ctrl+C; it worked for us!
<br>

### Test motors manually via terminal

- Open/Close the gripper:
<br>

      ros2 topic pub -1 /gripper_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{joint_names: ['6'], points: [{positions: [1.7], time_from_start: {sec: 1, nanosec: 0}}]}"

> [!WARNING]
> Our joints are called from 1 to 6 (base to gripper) but if it's not the case for you, just modify the inside of the ['']

- Move the arm (Example: Return to rest position):

      ros2 topic pub -1 /arm_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{joint_names: ['1', '2', '3', '4', '5'], points: [{positions: [0, 0, 0, 0, 0], time_from_start: {sec: 2, nanosec: 0}}]}"

You can try replacing a 0 with 1.57 (rad) to see the joints move.















    
