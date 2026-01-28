#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get the package directory
    pkg_dir = get_package_share_directory('vario700_sensorrig')
    
    # Read URDF file properly with context manager to ensure clean resource handling
    urdf_path = os.path.join(pkg_dir, 'urdf', 'vario700_sensorrig.urdf')
    with open(urdf_path, 'r') as urdf_file:
        robot_description_content = urdf_file.read()
    
    # Declare launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )
    
    # Robot state publisher: 
    # Currently opens urdf with pointclouds manually registered to tractor hood.
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'robot_description': robot_description_content
        }]
    )
    
    # TF2 static transform publisher for map to odom
    # To-Do:  should be replaced by actual localization system
    map_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='map_to_odom_static',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        output='screen'
    )
    
    # TF2 static transform publisher for odom to base_link
    # To-Do:  should be replaced by actual odometry system
    odom_to_base_link = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='odom_to_base_link_static',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_link'],
        output='screen'
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        robot_state_publisher,
        map_to_odom,
        odom_to_base_link,
    ])
