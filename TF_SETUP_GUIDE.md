# TF Tree Setup Guide for Vario700 Sensorrig with ZED Camera

## Overview

This guide explains how to properly display your robot model with ZED camera integration in RViz/Foxglove using the correct TF tree structure.

## TF Tree Structure

The complete TF tree should look like this:

```
map
└── odom
    └── base_link
        └── sensorrig
            └── os_sensor
                ├── os_lidar
                ├── os_sensor_imu
                ├── camera/rear_left
                ├── camera/rear_mid
                ├── camera/rear_right
                ├── camera/side_left
                ├── camera/side_right
                └── zed_camera_link
                    ├── zed_left_camera_frame
                    │   └── zed_imu_link
                    └── zed_right_camera_frame
```

## ZED Camera Transforms

Your ZED camera publishes these transforms:
- `zed_left_camera_frame` → `zed_imu_link`
- `map` → `odom` → `zed_camera_link`

## Setup Instructions

### 1. Build the Package

```bash
cd /home/gunreben/ros2_ws
colcon build --packages-select vario700_sensorrig
source install/setup.bash
```

### 2. Launch the Robot Model

```bash
# Launch the robot model with static transforms
ros2 launch vario700_sensorrig zed_integration.launch.py

# Or if you want to use simulation time
ros2 launch vario700_sensorrig zed_integration.launch.py use_sim_time:=true
```

### 3. Play Your ROS2 Bag

```bash
# Play your bag with ZED camera transforms
ros2 bag play your_bag_file --clock
```

### 4. View in RViz

```bash
# Launch RViz
rviz2

# In RViz:
# 1. Set Fixed Frame to "map"
# 2. Add RobotModel display
# 3. Add TF display to see the transform tree
# 4. Add any sensor data displays (PointCloud2, Image, etc.)
```

### 5. View in Foxglove

1. Open Foxglove Studio
2. Connect to your ROS2 bag or live data
3. Add 3D panel
4. Set the coordinate frame to "map"
5. Add RobotModel and TF displays

## Important Notes

### Static Transforms

The launch file includes static transforms for:
- `map` → `odom` (identity transform - replace with your localization)
- `odom` → `base_link` (identity transform - replace with your odometry)

**You should replace these with your actual localization and odometry systems.**

### ZED Camera Integration

The URDF now includes:
- `zed_camera_link`: Main ZED camera reference frame
- `zed_left_camera_frame`: Left camera frame (as published by ZED)
- `zed_right_camera_frame`: Right camera frame
- `zed_imu_link`: IMU frame (as published by ZED)

### Coordinate Frame Alignment

Make sure your ZED camera transforms are properly aligned:
- The ZED camera should be publishing `zed_left_camera_frame` → `zed_imu_link`
- The ZED camera should be publishing `map` → `odom` → `zed_camera_link`

## Troubleshooting

### TF Tree Issues

1. **Check TF tree**: `ros2 run tf2_tools view_frames`
2. **Check specific transform**: `ros2 run tf2_ros tf2_echo <parent_frame> <child_frame>`
3. **List all frames**: `ros2 run tf2_ros tf2_monitor`

### Common Problems

1. **Missing transforms**: Ensure your ZED camera is publishing the required transforms
2. **Timing issues**: Make sure all nodes are using the same time source
3. **Frame naming**: Verify frame names match exactly between URDF and published transforms

### Debug Commands

```bash
# Check if transforms are being published
ros2 topic list | grep tf

# Monitor TF tree
ros2 run tf2_tools view_frames

# Check specific transform
ros2 run tf2_ros tf2_echo map base_link

# Visualize TF tree
ros2 run rqt_tf_tree rqt_tf_tree
```

## Next Steps

1. Replace static transforms with your actual localization system
2. Add sensor data visualization (LiDAR, cameras, IMU)
3. Configure RViz/Foxglove displays for your specific use case
4. Test with your actual robot data
