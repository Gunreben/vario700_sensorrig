# vario700_sensorrig

⚠️ **This package is currently in development.**

## Description

This package includes the 3D files for the Fendt Vario 700 series, extracted from Farming Simulator 2022 with friendly permission from the creators [Schnibbl Modding](https://www.farming-simulator.com/mod.php?mod_id=243590&title=fs2022), as well as the experimental sensor setup from Smart Farming Lab - Leipzig University.

### Sensor Configuration

**Currently included in URDF:**
- **Ouster OS-128** - Front-mounted LiDAR
- **5x ArkCam Basic+ Mini** - Surround Mono Vision cameras
- **ZED 2i mini** - Front-mounted stereo camera

**Planned additions (not yet in URDF):**
- Blickfeld QB2 LiDAR (rear-mounted)
- Novatel OEM7 GNSS

## Prerequisites

- ROS2 (any distribution)
- `xacro` package for your ROS2 version

To install xacro:
```bash
sudo apt install ros-<your-ros2-distro>-xacro
```

## Calibration Sources

Camera positions shifted during 2025, so multiple calibration sets exist:

| Source     | Period                     | Notes                                  |
|------------|----------------------------|----------------------------------------|
| `msa`      | before 2025-09-27 (default)| Original MSA calibration               |
| `msa_new`  | after 2025-09-27           | Updated MSA calibration after shift    |
| `kalibr`   | 2025-10-22                 | Final manual calibration using Kalibr  |

Each source selects a matching URDF (extrinsics / TF tree) and camera intrinsics set.
When replaying recorded data, pick the source that matches the recording date.

## Usage

Run the robot state publisher (uncalibrated):
```bash
ros2 launch vario700_sensorrig robot_tf.launch.py
```

Run with calibrated transforms and camera intrinsics (default: `msa`):
```bash
ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py
ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py calibration_source:=msa_new
ros2 launch vario700_sensorrig robot_tf_calibrated.launch.py calibration_source:=kalibr
```
