#include "json2.js"

#include "utils.js"


// ============================================================
// Configuration
// ============================================================

// Location of timelapseConfig.json
var configDirectory = File($.fileName).parent;

var configFile = new File(
    configDirectory + "/timelapseConfig.json"
);


// ============================================================
// Month names
// ============================================================

var monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
];


// ============================================================
// Read configuration
// ============================================================

if (!configFile.exists) {

    alert(
        "timelapseConfig.json not found:\n" +
        configFile.fsName
    );

    throw new Error("timelapseConfig.json not found");
}


configFile.open("r");

var configJsonString = configFile.read();

configFile.close();


var configData = JSON.parse(configJsonString);


// Make sure config is an array
if (!(configData instanceof Array)) {

    alert(
        "timelapseConfig.json must contain " +
        "an array of configuration objects."
    );

    throw new Error(
        "timelapseConfig.json must contain an array"
    );
}


// ============================================================
// Helper: save configuration
// ============================================================

function saveConfig() {

    configFile.open("w");

    configFile.write(
        JSON.stringify(configData, null, 3)
    );

    configFile.close();
}


// ============================================================
// Process every configuration entry
// ============================================================

for (
    var configIndex = 0;
    configIndex < configData.length;
    configIndex++
) {

    var config = configData[configIndex];


    // --------------------------------------------------------
    // Validate configuration
    // --------------------------------------------------------

    if (
        config.name === undefined ||
        config.width === undefined ||
        config.height === undefined ||
        config.resolution === undefined ||
        config.id === undefined ||
        config.month === undefined ||
        config.year === undefined ||
        config.inputPath === undefined ||
        config.outputPath === undefined ||
        config.imageNaming === undefined ||
        config.imageNaming.pre === undefined ||
        config.imageNaming.sep === undefined ||
        config.imageNaming.enu === undefined
    ) {

        alert(
            "Invalid configuration at index " +
            configIndex +
            ".\n\n" +
            "Required fields:\n" +
            "name\n" +
            "width\n" +
            "height\n" +
            "resolution\n" +
            "id\n" +
            "month\n" +
            "year\n" +
            "inputPath\n" +
            "outputPath\n" +
            "imageNaming.pre\n" +
            "imageNaming.sep\n" +
            "imageNaming.enu"
        );

        throw new Error("Invalid configuration");
    }


    // --------------------------------------------------------
    // Job information
    // --------------------------------------------------------

    var jobName = config.name;

    alert(
        "Running " +
        jobName +
        " job."
    );


    // --------------------------------------------------------
    // Read configuration values
    // --------------------------------------------------------

    var width = config.width;
    var height = config.height;
    var resolution = config.resolution;

    var id = config.id;
    var month = config.month;
    var year = config.year;

    var inputPath = config.inputPath;
    var outputPath = config.outputPath;

    var imageNaming = config.imageNaming;


    // --------------------------------------------------------
    // Validate month
    // --------------------------------------------------------

    if (month < 1 || month > 12) {

        alert(
            "Invalid month in " +
            jobName +
            " job.\n\n" +
            "Month must be between 1 and 12."
        );

        throw new Error("Invalid month");
    }


    // --------------------------------------------------------
    // Generate PSD name
    // --------------------------------------------------------

    var psdName =
        id +
        "_" +
        monthNames[month - 1] +
        "_" +
        year;


    // --------------------------------------------------------
    // Resolve input/output paths
    // --------------------------------------------------------

    var inputFolder = new Folder(
        configDirectory +
        "/" +
        inputPath
    );

    var outputFolder = new Folder(
        configDirectory +
        "/" +
        outputPath
    );


    // --------------------------------------------------------
    // Create output folder
    // --------------------------------------------------------

    if (!outputFolder.exists) {

        if (!outputFolder.create()) {

            alert(
                "Could not create output folder:\n" +
                outputFolder.fsName +
                "\n\n" +
                "Job: " +
                jobName
            );

            throw new Error(
                "Could not create output folder"
            );
        }
    }


    // ========================================================
    // Create Photoshop document
    // ========================================================

    var newTimelapseDocument = app.documents.add(
        width,
        height,
        resolution,
        psdName,
        NewDocumentMode.RGB,
        DocumentFill.TRANSPARENT
    );


    // ========================================================
    // Check input folder
    // ========================================================

    if (!inputFolder.exists) {

        alert(
            "Input folder not found:\n" +
            inputFolder.fsName +
            "\n\n" +
            "Job: " +
            jobName
        );

        newTimelapseDocument.close(
            SaveOptions.DONOTSAVECHANGES
        );

        continue;
    }


    // ========================================================
    // Import images
    // ========================================================

    var imagesList = inputFolder.getFiles();

    for (var i = 0; i < imagesList.length; i++) {

        var image = imagesList[i];

        if (
            image instanceof File &&
            /\.(jpg|jpeg|png|gif|bmp)$/i.test(image.name)
        ) {

            placeFile(image);
        }
    }


    // ========================================================
    // Check number of images
    // ========================================================

    var layers = newTimelapseDocument.artLayers;


    if (layers.length == 0) {

        alert(
            "No images found in input folder:\n" +
            inputFolder.fsName +
            "\n\n" +
            "Job: " +
            jobName
        );

        newTimelapseDocument.close(
            SaveOptions.DONOTSAVECHANGES
        );

        continue;
    }


    if (layers.length % 4 != 0) {

        alert(
            "Number of input images is not divisible by 4.\n\n" +
            "Job: " +
            jobName +
            "\n" +
            "Images: " +
            layers.length
        );

        newTimelapseDocument.close(
            SaveOptions.DONOTSAVECHANGES
        );

        continue;
    }


    // ========================================================
    // Separate images into groups of 4
    // ========================================================

    var groupNumber = 0;

    while (layers.length > 0) {

        var group = newTimelapseDocument.layerSets.add();

        group.name =
            imageNaming.pre +
            imageNaming.sep +
            (
                imageNaming.enu +
                groupNumber
            );

        groupNumber++;


        for (var i = 0; i < 4; i++) {

            layers[layers.length - 1].move(
                group,
                ElementPlacement.PLACEATEND
            );

            layers = newTimelapseDocument.artLayers;
        }
    }


    // ========================================================
    // Process groups
    // ========================================================

    var groups = newTimelapseDocument.layerSets;


    for (var i = 0; i < groups.length; i++) {


        // ----------------------------------------------------
        // Set visibility
        // ----------------------------------------------------

        for (var j = 0; j < groups.length; j++) {

            if (j != i) {

                groups[j].visible = false;

            } else {

                groups[j].visible = true;
            }
        }


        // ----------------------------------------------------
        // Position images
        // ----------------------------------------------------

        var group = groups[i];


        for (
            var j = 0;
            j < group.artLayers.length;
            j++
        ) {

            var photo = group.artLayers[j];


            // Top-left
            if (j == 0) {

                photo.translate(
                    -photo.bounds[0],
                    -photo.bounds[1]
                );


            // Bottom-right
            } else if (j == 1) {

                photo.translate(
                    newTimelapseDocument.width -
                    photo.bounds[2],

                    newTimelapseDocument.height -
                    photo.bounds[3]
                );


            // Bottom-left
            } else if (j == 2) {

                photo.translate(
                    -photo.bounds[0],

                    newTimelapseDocument.height -
                    photo.bounds[3]
                );


            // Top-right
            } else if (j == 3) {

                photo.translate(
                    newTimelapseDocument.width -
                    photo.bounds[2],

                    -photo.bounds[1]
                );
            }
        }


        // ----------------------------------------------------
        // Export JPG
        // ----------------------------------------------------

        var jpgOptions = new JPEGSaveOptions();

        jpgOptions.quality = 12;


        var jpgFile = new File(
            outputFolder +
            "/" +
            group.name +
            ".jpg"
        );


        newTimelapseDocument.layerSets[i].merge();


        newTimelapseDocument.saveAs(
            jpgFile,
            jpgOptions,
            true,
            Extension.LOWERCASE
        );


        // ----------------------------------------------------
        // Undo merge
        // ----------------------------------------------------

        newTimelapseDocument.activeHistoryState =
            newTimelapseDocument.historyStates[
                newTimelapseDocument.historyStates.length - 2
            ];
    }


    // ========================================================
    // Save PSD
    // ========================================================

    var psdFile = new File(
        outputFolder +
        "/" +
        psdName +
        ".psd"
    );


    newTimelapseDocument.saveAs(psdFile);


    // ========================================================
    // Close document
    // ========================================================

    newTimelapseDocument.close(
        SaveOptions.DONOTSAVECHANGES
    );


    // ========================================================
    // Update configuration
    // ========================================================

    // Number of groups created:
    //
    // groupNumber starts at 0 and is incremented
    // after every group.
    //
    // Therefore, after processing:
    //
    // groupNumber = number of groups
    //
    // New enu = old enu + number of groups.

    config.imageNaming.enu =
        imageNaming.enu +
        groupNumber;


    // --------------------------------------------------------
    // Increment ID
    // --------------------------------------------------------

    config.id = id + 1;


    // --------------------------------------------------------
    // Increment month
    // --------------------------------------------------------

    config.month = month + 1;


    // --------------------------------------------------------
    // December -> January
    // --------------------------------------------------------

    if (config.month > 12) {

        config.month = 1;

        config.year = year + 1;
    }


    // --------------------------------------------------------
    // Save config immediately
    // --------------------------------------------------------

    saveConfig();


    // --------------------------------------------------------
    // Job finished
    // --------------------------------------------------------

    alert(
        jobName +
        " job finished successfully.\n\n" +
        "PSD: " +
        psdName +
        "\n" +
        "Groups: " +
        groupNumber +
        "\n" +
        "Next ID: " +
        config.id +
        "\n" +
        "Next month: " +
        monthNames[config.month - 1] +
        "\n" +
        "Next enu: " +
        config.imageNaming.enu
    );
}


// ============================================================
// Finished
// ============================================================

alert(
    "All timelapse jobs processed successfully."
);
