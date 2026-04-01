#!/usr/bin/env python3
"""
Unified launch file for robot_state_publisher and camera_info_publisher
with configurable calibration source.

Usage:
  ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py calibration_source:=msa
  ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py calibration_source:=msa_new
  ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py calibration_source:=kalibr
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def launch_setup(context, *args, **kwargs):
    """Deferred launch setup to resolve LaunchConfiguration values."""
    
    # Get resolved parameter values
    calibration_source = LaunchConfiguration('calibration_source').perform(context)
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context)
    
    # Package directories
    vario700_pkg_dir = get_package_share_directory('vario700_sensorrig')
    tractor_pkg_dir = get_package_share_directory('tractor_multi_cam_publisher')
    
    # Select URDF based on calibration source
    urdf_filename = f'vario700_sensorrig_{calibration_source}.urdf'
    urdf_path = os.path.join(vario700_pkg_dir, 'urdf', urdf_filename)
    
    if not os.path.exists(urdf_path):
        raise FileNotFoundError(
            f"URDF file not found: {urdf_path}\n"
            f"Valid calibration sources: 'msa', 'msa_new', 'kalibr'"
        )
    
    with open(urdf_path, 'r') as urdf_file:
        robot_description_content = urdf_file.read()
    
    calibration_path = os.path.join(tractor_pkg_dir, 'calibration', calibration_source)
    
    if not os.path.isdir(calibration_path):
        raise FileNotFoundError(
            f"Calibration directory not found: {calibration_path}\n"
            f"Valid calibration sources: 'msa', 'msa_new', 'kalibr'"
        )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time.lower() == 'true',
            'robot_description': robot_description_content
        }]
    )
    
    # Camera info publisher with calibration source specific path
    camera_info_publisher = Node(
        package='tractor_multi_cam_publisher',
        executable='camera_info_publisher',
        name='camera_info_publisher',
        output='screen',
        parameters=[{
            'calibration_path': calibration_path
        }]
    )
    
    zed_camera_info_publisher = Node(
        package='tractor_multi_cam_publisher',
        executable='zed_camera_info_publisher',
        name='zed_camera_info_publisher',
        output='screen',
        parameters=[{
            'calibration_path': calibration_path
        }]
    )
    
    # TF2 static transform publisher for map to odom
    # TODO: Replace with actual localization system
    map_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='map_to_odom_static',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        output='screen'
    )
    
    # TF2 static transform publisher for odom to base_link
    # TODO: Replace with actual odometry system
    odom_to_base_link = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='odom_to_base_link_static',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_link'],
        output='screen'
    )
    
    return [
        robot_state_publisher,
        camera_info_publisher,
        zed_camera_info_publisher,
        map_to_odom,
        odom_to_base_link,
    ]


def generate_launch_description():
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'calibration_source',
            default_value='msa',
            description="Calibration source to use: 'msa', 'msa_new', or 'kalibr'"
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation (Gazebo) clock if true'
        ),
        
        # Deferred setup to resolve configurations
        OpaqueFunction(function=launch_setup),
    ])
