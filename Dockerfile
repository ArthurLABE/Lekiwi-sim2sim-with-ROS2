FROM osrf/ros:humble-desktop

# Mise à jour et installation des dépendances du robot
RUN apt-get update && apt-get install -y \
    ros-humble-pinocchio \
    ros-humble-ign-ros2-control \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-moveit \
    ros-humble-moveit-setup-assistant \
    ros-humble-joint-state-publisher \
    ros-humble-ros-gz \
    # ---> LES AJOUTS POUR LA CAMÉRA <---
    ros-humble-ros-gz-image \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Configuration de l'environnement par défaut
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
