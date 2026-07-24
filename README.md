# Lekiwi-simulation-with-ROS2

In this repository, we explain step by step how to create a dataset of simulated pick&amp;place episodes from scratch, using ROS2, Gazebo and MoveIt.

Our goal is to train our robot LeKiwi to perform tasks in the real world, without necessarily having to create a real dataset via teleoperation.

We will later be able to compare the results obtained with the simulated dataset (sim2real) and those obtained with the dataset created via teleoperation.


<img width="70%" alt="Screenshot from 2026-06-03 14-17-24" src="https://github.com/user-attachments/assets/be7d369e-651b-4966-b603-1c184bfc3429" />

_Screenshot of the LeKiwi robot performing a pick and place episode._

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
> [!IMPORTANT]
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
  ros2 run lekiwi_application ep_cplt
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
```

Once the blank GUI opens, here are the steps to follow to load the controller:

- In the top-left menu, click on Plugins.

- Navigate to Robot Tools > Joint Trajectory Controller.

In the new panel that appears, configure the two dropdown menus:

- Controller Manager: Select /controller_manager.

- Controller: Select arm_controller.

The 5 sliders for your arm's joints will appear. You can now move the sliders with the mouse to control the robot live in Gazebo.




## VII. SimtoSim tests

### First try 

After recording a 141-episode dataset and fine-tuning SmolVLA, we tested the model in the exact same simulation environment used for training. We didn't add any new elements; our goal was simply to test if the robot could replicate the episodes it saw in the dataset (still with small position randomizations for the box and the deposit area).

As shown in the following video, the arm struggled to grasp the box. The robot navigated perfectly toward the target before stopping, but the arm consistently failed to pick up the box, meaning the mission was never successfully completed.



> Video link : https://youtube.com/shorts/0_pIW6L7TGU?feature=share


>[!NOTE]
>This video is not the final version that will be produced at the end of this section.


Our Hypotheses:

- Lack of visual perspective: We hypothesized that the camera images lacked depth cues. With only the box and the deposit area in an empty gray environment, it was extremely difficult for the model to estimate distances. To solve this primary issue, we added a checkerboard floor to the simulation, which should provide strong visual anchors for depth and perspective estimation.

- Lack of corrective actions: We also realized that our simulated dataset lacked recovery behaviors. In a human-teleoperated dataset, the operator naturally makes slight imprecisions and continuously corrects them with the joystick, teaching the AI how to recover from drift. In contrast, our simulated simulation generates mathematically perfect trajectories. 
We initially considered injecting random noise into the arm's approach phase to mimic the imperfect, corrective movements of a human operator. However, we decided against it to avoid Causal Confusion during the Behavioral Cloning process.
In a programmatically generated dataset (like ours with MoveIt), if we script an intentional error (e.g., "move 3cm to the right, then correct"), the action log explicitly records that off-center movement as the correct desired action for that specific visual frame.
If we injected this noise, the VLA model would learn the wrong cause-and-effect: it would look at the box and learn to intentionally approach it from a skewed angle, rather than learning how to recover from drift. 
To maintain the mathematical coherence of the dataset, we kept the programmed trajectories strictly perfect and chose to rely entirely on visual domain randomization (like the checkerboard floor) to help the model generalize its perspective.



### Second try : Checkerboard  

<img width="50%" alt="Screenshot" src="https://github.com/user-attachments/assets/3fc8d922-12e2-4bf3-a4a7-1cba8a6d1514" />

We tested another 141-episode dataset, similar to the previous one, but it didn't go as expected: the moving base wasn't driving straight. Before explaining this result, we must note an issue encountered during the dataset recording. A physics glitch in Gazebo caused the stats.json file to record a maximum wheel velocity of over 37,000 rad/s, which is physically impossible. We had visually verified the 141 episodes before fine-tuning the model to ensure the training data looked good, but we couldn't see this hidden metric issue coming.

This stats.json file is responsible for "denormalizing" the model's outputs (converting them from values between [-1, 1] back to real physical values) to send to the robot during inference. However, even after manually fixing these statistical outliers to realistic limits, the robot's behavior remained erratic. We concluded that the true cause of the failure was the checkerboard itself: its high-frequency texture caused a visual "aliasing" effect. This created an Out-of-Distribution (OOD) shock for the Vision Transformer, causing the AI to panic and output extreme action values.

<br>


### Third try : Bigger dataset  

After this unsuccessful test, we took a step back to try another hypothesis. We thought that 141 episodes were simply not enough to compensate for the lack of natural noise in the arm's movements. Since we had already established the risk of injecting artificial noise during the dataset generation, our alternative was to increase the sheer volume of data. We expanded the dataset to 265 episodes. We believe this broader dataset will allow the model to perform better, particularly during the grasping phase.

>[!IMPORTANT]
> **Model Architecture Update:** We switched from SmolVLA to ACT after observing a significant performance gain. We can attribute this improvement to the contrast between ACT’s "action chunking" mechanism—which produces smooth trajectories—and SmolVLA’s token-based approach, which ultimately proves excessive for deterministic tasks such as "grasp the red box and place it on the orange zone." Moving forward, all models in this repository will be based on the ACT architecture.

We evaluated the ACT model across several fine-tuning checkpoints (5k, 10k, 20k, 40k, and 60k steps), testing chunk sizes of both 10 and 100 actions for each. While our current comparison is purely qualitative, the initial results are highly encouraging. We have not yet extracted formal quantitative metrics; this limitation is discussed in the final section of this repository. 
The video below shows the robot successfully performing the task for one of the tested configurations.

> Video link : https://youtu.be/08YMGowBGiA

Across all the successful tests, the distance between the center of the drop zone and the box was unsatisfactory. This is a parameter we should have taken into account for the evaluation, from the time the dataset was recorded right up to the present. In the absence of metrics, we can only assume that this lack of precision is due to overfitting: a reproduction of joint positions rather than a true understanding of the task.

<br>


### Fourth try : Domain randomization

<img width="50%" alt="Screenshot from 2026-07-06 10-34-38" src="https://github.com/user-attachments/assets/7fa5e85a-33f0-4b9a-9133-b3da0d64827f" />


While fine-tuning the third model, we generated a new dataset with multiple variations to improve the model's generalization capabilities. We added randomly colored distractors (spheres, cylinders, and cubes) to the environment. Furthermore, the target box and the deposit area now change colors randomly for each episode, in addition to having their positions slightly randomized. The goal is to force the AI to focus on the geometric features of the task rather than memorizing specific colors.

We trained ACT models (using the same checkpoints as before) on a dataset of 343 demonstrations; the results proved relatively satisfactory, even though we do not yet have metrics to substantiate our conclusions. The model was able to perform the task in the presence of new background distractors, demonstrating that it had correctly understood both the task and the irrelevant elements. The presentation video is available via the link below, as with the previous section.

> Video link : https://youtu.be/DQq9r6hJD5o 

<br>


### Fifth try : Grasp consistency 

During our first attempt with SmolVLA, we noticed the arm struggling to successfully grasp the box. For this fifth try, we wanted to investigate if the issue stemmed from a lack of consistency in the grasping trajectories. In Imitation Learning, if the model sees similar images but is mapped to different actions (e.g., three different programmed ways to approach the same box), it can suffer from "Action Aliasing" and become confused. We wanted to see if this model could achieve better grasping success rate compared to other models using multiple trajectories.

To verify this, we filtered our datasets (merging the basic one and the domain-randomized one) to include only one consistent type of grasp out of the three originally programmed.

We were unable to achieve a higher success rate for the grasping task; this could be attributed to the fact that we only had 37 demonstrations of the "top-down" trajectory—the one we had selected for this trial. We should have prioritized the grasping trajectory that was most prevalent in the dataset to avoid this bias. Unfortunately, we no longer have the time required to repeat the experiment.


### Final try : Merged dataset

For this final experiment, we wanted to determine whether a merged dataset—comprising the 265 demonstrations from the reference dataset and the 343 demonstrations from the domain randomization dataset—could outperform the one using only domain randomization. We trained this model for 100,000 steps, with checkpoints saved every 20,000 steps.

Qualitative evaluation of these models showed that using demonstrations from the baseline configuration was less effective. Indeed, models trained with domain randomization achieved a higher success rate than those trained on the merged dataset. This holds true for evaluations based on the baseline configuration as well as those based on domain randomization. However, this assertion is based solely on the observation of multiple tests of each model; it is not quantified and must therefore be treated with caution. 

<br>

## Conclusion, results and areas for improvement

During this work we had a qualitative approach that seemed good in the beginning but it appread that we should have done differently certain things : 
             
                               
### Quantitative approach

To make our approach more scientific, we should have evaluated our models using precise metrics. For example, we could have measured:
- The distance between the center of the box and the center of the deposit area.
- Grasp quality (normal force, sliding force, and the alignment between the gripper's fingers and the box center).

With these metrics, we could have distributed rewards for each demonstration in the dataset. This would have given us clear thresholds to compare the success rates of our models with real precision. 

Without objective numbers, claiming that one model is better than another lacks scientific proof. This is why our current visual approach remains imprecise and should be considered as a qualitative observation.

<br>

### Dataset Recording Limitations : The Grasping Approach

During the dataset recording phase, we used inverse kinematics from MoveIt2 for the grasping approach. After trying several methods, this was the most reliable one, but we had to make a compromise. 

In the code, we commanded the robot to stop at a fixed distance (around 33 cm) from the center of the box, and then MoveIt2 calculated the joint values needed to grasp it. The problem is that even when we changed the box's position in the environment, the robot always approached it from the exact same distance (minus some slight wheel slip). 

As a result, the arm had almost the exact same joint positions for every single grasp in the dataset. This lack of diversity is a major issue for generalization and heavily promotes overfitting. We should have added randomness to this approach distance. At the time, we chose a fixed distance because adding randomness caused MoveIt2's success rate to drop significantly (around 2/5 successful grasps). We chose stability to record the dataset faster, but taking more time to fix this would have resulted in much better training data.




