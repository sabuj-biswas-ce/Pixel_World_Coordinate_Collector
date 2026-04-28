# Pixel_World_Coordinate_Collector
## 📌 Purpose

This tool is designed to collect **pixel coordinates** and their corresponding **real-world coordinates** for use in geometric transformations.

It generates a structured CSV file containing matched coordinate pairs, which can be directly used for:

* **Homography estimation**
* **Perspective correction**
* **Camera calibration**

---

## 🧠 How It Helps

In many computer vision and mapping tasks, you need accurate correspondences between image space and real-world space. Manually collecting these points is time-consuming and error-prone.

This tool simplifies the process by allowing users to:

* Click points directly on an image (pixel coordinates)
* Input corresponding real-world coordinates
* Automatically store all data in a clean CSV format

---

## 🎯 Key Applications

* **Homography**
  Compute transformation between image plane and real-world plane

* **Perspective Correction**
  Remove distortion and obtain a top-down (bird’s-eye) view

* **Camera Calibration**
  Establish relationships between image pixels and physical coordinates

---

## 📊 Output

The tool exports a CSV file containing:

* Image path
* Pixel coordinates (u, v)
* Real-world coordinates (X, Y)

This dataset can be directly used in libraries like OpenCV for further processing.


## 🚀 Features

* Load single or multiple images
* Click to add Ground Control Points (GCPs)
* Assign real-world coordinates (X, Y)
* Zoom and pan for precise selection
* View all points in a table (across multiple images)
* Delete or edit points easily
* Export all data to CSV

---

## 🖥️ Demo Workflow

1. Load an image
2. Click on a point in the image
3. Enter real-world coordinates
4. Repeat for multiple points/images
5. Save results to CSV

---

## 📦 Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

### requirements.txt

```
opencv-python
numpy
```

> ⚠️ Tkinter is included with Python by default (no need to install separately)

---

## ▶️ How to Run

```bash
python Pixel_World_Coordinate_Collector.py
```

## 🧠 Use Cases

* Photogrammetry
* Camera calibration
* Mapping and GIS projects
* Image-to-world coordinate transformation
* Data collection for computer vision
---

## 🛠️ Built With

* Python
* Tkinter (GUI)
* OpenCV
* NumPy

---

## ⚠️ Notes

* Supports common image formats: PNG, JPG, BMP, TIFF
* All points from all images are saved into a single CSV file
* Coordinates are stored in meters (user-defined)

---

## 🙌 Acknowledgements

Built using:

* OpenCV for image processing
* Tkinter for GUI
* NumPy for numerical operations
* GUI Developed with assistance from Al Tool (ChatGPT) 

---

## 📧 Contact

If you have suggestions or improvements, feel free to open an issue or pull request.
