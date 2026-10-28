# Photoshop Timelapse Automation

For stabilized videos of the front, both profiles, and the top of the head, see [VIDEO_README.md](VIDEO_README.md). On Windows, run `Generate_Face_Videos.cmd` to choose views and regenerate the movies.

For body-change videos, run `Generate_Refined_Body_Videos.cmd`; see [BODY_REFINED_README.md](BODY_REFINED_README.md) for torso stabilization, cropping, and playback settings. The original head-aligned body workflow is documented in [BODY_VIDEO_README.md](BODY_VIDEO_README.md).

A collection of Adobe Photoshop ExtendScript (`.jsx`) and Python utilities for automating the creation and post-processing of timelapse image sequences.

The main workflow imports images into Photoshop, groups them into sets of four, positions them at the four corners of a document, exports each group as a JPG, and saves the resulting Photoshop document as a PSD.

Additional scripts are provided for renaming exported files and normalizing layer names in existing PSD files.

---

## Features

* Process multiple timelapse jobs from a single configuration file.
* Recursive image processing.
* Configurable document dimensions and resolution.
* Configurable input/output directories.
* Automatic PSD naming based on:

  * ID
  * Month
  * Year
* Automatic incrementing of ID, month, and year.
* Automatic continuation of image/group numbering.
* Groups four images into a single timelapse frame.
* Positions the four images at the four corners of the document.
* Exports each group as a high-quality JPG.
* Saves the complete Photoshop document as a PSD.
* Recursive PSD layer/group renaming.
* Python utility for recursive image filename renaming.

---

# Requirements

## Photoshop

The main scripts use Adobe Photoshop ExtendScript.

The scripts are intended to be executed from Photoshop's scripting environment.

## Python

The filename-renaming utility requires Python.

The Python script uses only the standard library.

---

# Project Structure

A typical project can look like this:

```text
Timelapse/
│
├── Scripts/
│   └── timelapse.jsx
│
├── timelapseConfig.json
│
├── Input/
│   ├── Face/
│   │   ├── image001.jpg
│   │   ├── image002.jpg
│   │   └── ...
│   │
│   └── Body/
│       ├── image001.jpg
│       ├── image002.jpg
│       └── ...
│
└── Output/
    ├── Face/
    │   ├── face_1256.jpg
    │   ├── face_1257.jpg
    │   └── 49_August_2026.psd
    │
    └── Body/
        ├── body_510.jpg
        ├── body_511.jpg
        └── 20_August_2026.psd
```

The exact folder structure can be changed using `inputPath` and `outputPath` in the configuration.

---

# Main Timelapse Script

The main Photoshop script processes every configuration entry independently.

For each job it:

1. Reads the configuration.
2. Generates the PSD name.
3. Opens the configured input directory.
4. Imports all supported images.
5. Groups images into sets of four.
6. Positions the four images.
7. Exports each group as a JPG.
8. Restores the Photoshop document state.
9. Saves the complete PSD.
10. Updates the configuration.
11. Moves to the next job.

---

## Configuration

The main configuration file is:

```text
timelapseConfig.json
```

It contains an array of jobs.

Example:

```json
[
   {
      "name": "Face",
      "width": 3072,
      "height": 4092,
      "resolution": 300,
      "id": 49,
      "month": 8,
      "year": 2026,
      "inputPath": "../Input/Face",
      "outputPath": "../Output/Face",
      "imageNaming": {
         "pre": "face",
         "sep": " ",
         "enu": 1256
      }
   },
   {
      "name": "Body",
      "width": 3072,
      "height": 4092,
      "resolution": 300,
      "id": 20,
      "month": 8,
      "year": 2026,
      "inputPath": "../Input/Body",
      "outputPath": "../Output/Body",
      "imageNaming": {
         "pre": "body",
         "sep": " ",
         "enu": 510
      }
   }
]
```

---

# Configuration Fields

## `name`

Human-readable name of the job.

Example:

```json
"name": "Face"
```

When the script starts processing the job, it displays:

```text
Running Face job.
```

---

## `width`

Photoshop document width in pixels.

```json
"width": 3072
```

---

## `height`

Photoshop document height in pixels.

```json
"height": 4092
```

---

## `resolution`

Photoshop document resolution.

```json
"resolution": 300
```

---

## `id`

Current timelapse ID.

The ID is used to generate the PSD filename.

Example:

```json
"id": 49
```

produces:

```text
49_August_2026.psd
```

After a successful job, the ID is automatically incremented:

```text
49 → 50
```

---

## `month`

Current month represented as a number from `1` to `12`.

Example:

```json
"month": 8
```

produces:

```text
August
```

The month is automatically incremented after a successful job.

December is handled automatically:

```text
12 / 2026
    ↓
1 / 2027
```

---

## `year`

Current year.

Example:

```json
"year": 2026
```

The year is incremented automatically when the month changes from December to January.

---

## `inputPath`

Directory containing the source images.

Example:

```json
"inputPath": "../Input/Face"
```

Paths are resolved relative to the directory containing the script/configuration.

---

## `outputPath`

Directory where generated JPGs and PSD files are stored.

Example:

```json
"outputPath": "../Output/Face"
```

The directory is created automatically if it doesn't exist.

---

# Image Naming

The `imageNaming` object controls the names of generated groups/JPG files.

```json
"imageNaming": {
   "pre": "face",
   "sep": " ",
   "enu": 1256
}
```

### `pre`

Prefix used for generated group names.

```json
"pre": "face"
```

### `sep`

Separator between the prefix and number.

```json
"sep": " "
```

This produces:

```text
face 1256
face 1257
face 1258
```

### `enu`

Starting group number.

```json
"enu": 1256
```

If three groups are generated:

```text
face 1256
face 1257
face 1258
```

the configuration is automatically updated to:

```json
"enu": 1259
```

This allows the next execution to continue numbering automatically.

---

# PSD Naming

The PSD filename is generated automatically.

The format is:

```text
<ID>_<Month>_<Year>.psd
```

For example:

```json
"id": 49,
"month": 8,
"year": 2026
```

produces:

```text
49_August_2026.psd
```

`psdName` is therefore **not required in the configuration**.

---

# Image Grouping

The main script processes images in groups of four.

For example:

```text
image01.jpg
image02.jpg
image03.jpg
image04.jpg
image05.jpg
image06.jpg
image07.jpg
image08.jpg
```

becomes:

```text
Group 1
├── image01.jpg
├── image02.jpg
├── image03.jpg
└── image04.jpg

Group 2
├── image05.jpg
├── image06.jpg
├── image07.jpg
└── image08.jpg
```

Each group represents one exported timelapse frame.

The number of input images must be divisible by four.

---

# Image Positioning

The four images are positioned at the four corners of the Photoshop document.

```text
┌─────────────────────────────┐
│                             │
│  Image 0         Image 3    │
│                             │
│                             │
│                             │
│  Image 2         Image 1    │
│                             │
└─────────────────────────────┘
```

The images are aligned to the document edges using their layer bounds.

---

# JPG Export

Each group is merged and exported as a JPG.

JPEG quality:

```text
12
```

Example output:

```text
face 1256.jpg
face 1257.jpg
face 1258.jpg
```

---

# PSD Output

After all groups have been processed, the original grouped layer structure is preserved and the document is saved as a PSD.

Example:

```text
49_August_2026.psd
```

---

# Automatic Configuration Updates

The configuration is updated after every successfully completed job.

For example, before execution:

```json
{
   "id": 49,
   "month": 8,
   "year": 2026,
   "imageNaming": {
      "enu": 1256
   }
}
```

After processing 10 groups:

```json
{
   "id": 50,
   "month": 9,
   "year": 2026,
   "imageNaming": {
      "enu": 1266
   }
}
```

This makes the configuration act as persistent state for the timelapse pipeline.

If December is processed:

```text
December 2026
     ↓
January 2027
```

the year is automatically incremented.

---

# PSD Layer Renaming Script

The repository also contains a Photoshop script for recursively processing existing PSD files.

It searches recursively for:

```text
.psd
```

files and opens them one by one.

It then recursively examines all layers and layer groups.

# Supported Image Formats

The Python utility recognizes:

```text
.jpg
.jpeg
.png
.gif
.bmp
.tif
.tiff
.webp
```

The Photoshop timelapse importer currently recognizes:

```text
.jpg
.jpeg
.png
.gif
.bmp
```

---

# Error Handling

The main script performs several checks before and during processing.

It checks:

* Whether `timelapseConfig.json` exists.
* Whether the configuration is an array.
* Whether required configuration fields exist.
* Whether the month is between 1 and 12.
* Whether the input directory exists.
* Whether any images were found.
* Whether the number of images is divisible by four.
* Whether the output directory can be created.

If a job cannot be processed, it is skipped rather than corrupting the Photoshop document.

The configuration is saved after each successfully completed job so that completed jobs retain their updated state even if a later job fails.

---

# Typical Workflow

A typical workflow is:

```text
1. Add source images
        ↓
2. Run Photoshop timelapse script
        ↓
3. Photoshop creates grouped PSD
        ↓
4. Groups are exported as JPGs
        ↓
5. PSD is saved
        ↓
6. Configuration counters are updated
        ↓
7. Optional PSD layer normalization
```

---

# Example

Starting configuration:

```json
{
   "name": "Face",
   "id": 49,
   "month": 8,
   "year": 2026,
   "imageNaming": {
      "pre": "face",
      "sep": " ",
      "enu": 1256
   }
}
```

Suppose the input directory contains 20 images.

The script creates:

```text
face 1256
face 1257
face 1258
face 1259
face 1260
```

and exports:

```text
face 1256.jpg
face 1257.jpg
face 1258.jpg
face 1259.jpg
face 1260.jpg
```

The PSD is:

```text
49_August_2026.psd
```

After successful processing, the configuration becomes:

```json
{
   "name": "Face",
   "id": 50,
   "month": 9,
   "year": 2026,
   "imageNaming": {
      "pre": "face",
      "sep": " ",
      "enu": 1261
   }
}
```

The next execution therefore continues automatically from:

```text
face 1261
```

---

# Notes

The main Photoshop script depends on the helper file:

```text
utils.js
```

because the image import operation uses:

```javascript
placeFile(image)
```

The project also includes:

```text
json2.js
```

for JSON handling in the ExtendScript environment.

Keep these files available when running the Photoshop scripts.

---
