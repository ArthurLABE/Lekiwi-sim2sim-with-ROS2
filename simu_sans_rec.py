#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from sensor_msgs.msg import Image, JointState
from geometry_msgs.msg import Pose

import pinocchio as pin
import numpy as np
import random
import cv2
from cv_bridge import CvBridge
import os
import time
import subprocess

class DatasetGeneratorNode(Node):
    def __init__(self):
        super().__init__('dataset_generator_node')
        
        # --- CONFIGURATION DU DATASET ---
        self.dataset_dir = './lerobot_dataset'
        os.makedirs(self.dataset_dir, exist_ok=True)
        self.episode_idx = 0
        self.bridge = CvBridge()
        
        # --- CONFIGURATION PINOCCHIO ---
        urdf_path = '/home/polytech/Documents/Stage_ISIR/ROS/lerobot_ws/src/lerobot_description/urdf/so101_base_compiled.urdf' # à ajuster si changement 

        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()
        # Au lieu de "gripper", on utilise notre nouveau point virtuel !
        self.ee_frame_id = self.model.getFrameId("tcp_link")
        
        # --- ACTION CLIENTS ---
        self.arm_client = ActionClient(self, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
        self.gripper_client = ActionClient(self, FollowJointTrajectory, '/gripper_controller/follow_joint_trajectory')

        # --- SUBSCRIBERS (Caméras) ---
        self.latest_img_base = None
        self.latest_img_pince = None
        
        self.sub_cam_base = self.create_subscription(Image, '/camera_base/image_raw', self.cam_base_cb, 10)
        self.sub_cam_pince = self.create_subscription(Image, '/camera_pince/image_raw', self.cam_pince_cb, 10)

    # ==========================================
    # CALLBACKS DES CAMÉRAS
    # ==========================================
    def cam_base_cb(self, msg):
        self.latest_img_base = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def cam_pince_cb(self, msg):
        self.latest_img_pince = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    # ==========================================
    # CINÉMATIQUE INVERSE (PINOCCHIO)
    # ==========================================
    def solve_ik(self, target_position):
        """Calcule les angles des moteurs (Focus sur la Position 3D uniquement)"""
        
        # 1. LE POINT DE DÉPART (Seed)
        # Au lieu de commencer les calculs avec le bras droit en l'air, 
        # on l'initialise dans une posture courbée vers la table.
        q = pin.neutral(self.model)
        q[0] = 0.0
        q[1] = 0.0
        q[2] = 0.0
        q[3] = 1.57
        q[4] = -1.57
        """ pos repos : q[0] = 0.0 ; q[1] = -1.7 ; q[2] = 1.57 ; q[3] = 0.76 ; q[4] = -1.57 """
        eps = 1e-4
        ITERS = 1000
        DT = 0.1
        
        for i in range(ITERS):
            pin.forwardKinematics(self.model, self.data, q)
            pin.updateFramePlacements(self.model, self.data)
            
            # 2. ERREUR 3D SEULEMENT
            # On cherche juste à amener le centre de la pince sur le point (X,Y,Z)
            # On ignore l'orientation (Roll, Pitch, Yaw) pour ne pas bloquer les 5 axes
            current_pos = self.data.oMf[self.ee_frame_id].translation
            err = current_pos - np.array(target_position)
            
            if np.linalg.norm(err) < eps:
                break
                
            # 3. JACOBIENNE DE TRANSLATION
            # On découpe la matrice pour ne garder que les mouvements en X, Y et Z (3 premières lignes)
            J = pin.computeFrameJacobian(self.model, self.data, q, self.ee_frame_id, pin.ReferenceFrame.LOCAL_WORLD_ALIGNED)
            J_trans = J[:3, :]
            
            v = - np.linalg.pinv(J_trans) @ err
            q = pin.integrate(self.model, q, v * DT)

        print(f" Box : X={target_position[0]:.4f}, Y={target_position[1]:.4f}, Z={target_position[2]:.4f}")
        print(f" Pince : X={current_pos[0]:.4f}, Y={current_pos[1]:.4f}, Z={current_pos[2]:.4f}")
        time.sleep(5)
        print("\n")

        return q[:5].flatten().tolist()

    # ==========================================
    # CONTRÔLE DES MOTEURS
    # ==========================================
    def send_movement(self, action_client, joint_names, positions, duration_sec):
        action_client.wait_for_server()
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = joint_names
        
        point = JointTrajectoryPoint()
        point.positions = [float(i) for i in positions]
        point.time_from_start = Duration(sec=duration_sec, nanosec=0)
        goal_msg.trajectory.points.append(point)
        
        future_goal = action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future_goal)
        goal_handle = future_goal.result()
        if not goal_handle.accepted:
            self.get_logger().error("Mouvement refusé !")
            return

        future_result = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, future_result)

    # ==========================================
    # LOGIQUE DE GÉNÉRATION D'ÉPISODE
    # ==========================================
    def teleport_entity_ign(self, name, x, y, z):
        """Fonction utilitaire pour téléporter un objet existant dans Gazebo"""
        try:
            # 1. Trouver le nom du monde actuel dans Gazebo
            out = subprocess.check_output(["ign", "service", "-l"], stderr=subprocess.DEVNULL).decode('utf-8')
            world_name = "empty"
            for line in out.split('\n'):
                line = line.strip()
                if line.startswith("/world/") and line.endswith("/set_pose"):
                    world_name = line.split("/")[2]
                    break
            
            # 2. Appeler le service de téléportation (set_pose)
            req = f"name: '{name}', position: {{x: {x}, y: {y}, z: {z}}}"
            cmd = [
                "ign", "service", "-s", f"/world/{world_name}/set_pose",
                "--reqtype", "ignition.msgs.Pose",
                "--reptype", "ignition.msgs.Boolean",
                "--timeout", "1000",
                "--req", req
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            pass

    def teleport_box(self, x, y, z):
        """Déplace la boîte rouge aux nouvelles coordonnées"""
        
        # 1. On tente de la créer (marchera uniquement au tout premier épisode)
        sdf_file = "/home/polytech/Documents/Stage_ISIR/ROS/lerobot_ws/src/lerobot_description/urdf/red_box.sdf"
        cmd_create = [
            "ros2", "run", "ros_gz_sim", "create",
            "-file", sdf_file,
            "-name", "ma_boite_rouge",
            "-x", str(round(x, 4)),
            "-y", str(round(y, 4)),
            "-z", str(round(z, 4))
        ]
        subprocess.run(cmd_create, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. On force la téléportation (marchera pour tous les épisodes suivants)
        self.teleport_entity_ign("ma_boite_rouge", x, y, z)
        
        self.get_logger().info(f"Boîte téléportée à : X={x:.2f}, Y={y:.2f}")
        time.sleep(0.5)

    def generate_random_target(self):
        """Génère un point (X,Y,Z) aléatoire dans l'espace de travail visuel"""
        # L'avant de votre robot correspond aux X Négatifs !
        x = random.uniform(-0.05, 0.05) 
        # Le bras est fixé à Y = -0.08, on centre la zone autour de lui
        y = random.uniform(-0.45, -0.25) 
        z = 0.015 # Hauteur sur la table
        return [x, y, z]

    def run_dataset_loop(self, num_episodes=10):
        # 0. On force la réception des toutes premières images pour être sûr que le pont est actif
        while self.latest_img_base is None or self.latest_img_pince is None:
            rclpy.spin_once(self, timeout_sec=0.1)
        
        for ep in range(num_episodes):
            self.episode_idx = ep
            print(f"\n====== DÉBUT DE L'ÉPISODE {ep} =====\n")
            
            # 1. Définir les zones aléatoires
            pick_pos = self.generate_random_target()
            place_pos = [0.05, -0.40, 0.015] #================================================//////////////////////////=constant arbitraire

            # 2. Téléporter la boîte au point de départ
            self.teleport_box(pick_pos[0], pick_pos[1], pick_pos[2])
            
            # 3. Approche au dessus de l'objet (Z + 10cm)
            #Bidouille pour avoir la pince alignée avec la box : 
            pick_pos[0] += 0.015
            approach_pos = [pick_pos[0], pick_pos[1], pick_pos[2] + 0.15]
            angles_approach = self.solve_ik(approach_pos)

            self.send_movement(self.gripper_client, ['6'], [1.7], 1) # Ouvrir pince
            time.sleep(1)
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_approach, 2)
            time.sleep(2)
            
            # 4. Descente et Saisie
            angles_pick = self.solve_ik(pick_pos)
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_pick, 1)
            time.sleep(1)
            self.send_movement(self.gripper_client, ['6'], [0.0], 1) # Fermer pince
            time.sleep(2)
            
            # 5. Lever l'objet et aller vers la cible (Z + 10cm)
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_approach, 2)
            time.sleep(2)

            approach_place = [place_pos[0], place_pos[1], place_pos[2] + 0.15]
            angles_place_up = self.solve_ik(approach_place)
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_place_up, 2)
            time.sleep(2)
            
            # 6. Descente et Lâcher
            angles_place = self.solve_ik(place_pos)
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_place, 1)
            time.sleep(4)
            self.send_movement(self.gripper_client, ['6'], [1.7], 1) # Ouvrir pince
            time.sleep(1)
            
            # 7. Retour position de repos
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], angles_place_up, 2) #pour pas bousculer en partant
            self.send_movement(self.arm_client, ['1', '2', '3', '4', '5'], [0.0, 0.0, 0.0, 0.0, 0.0], 2)
            
            print(f"===== FIN DE L'ÉPISODE {ep} =====")

def main(args=None):
    rclpy.init(args=args)
    node = DatasetGeneratorNode()
    
    # Lance la création de 10 épisodes
    node.run_dataset_loop(num_episodes=10)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()