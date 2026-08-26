// function found here:
// https://community.adobe.com/t5/photoshop/photoshop-scripts-for-image-layers-javascript/m-p/9903887
function placeFile(placeFile, newTimelapseDocument) {
  var curr_file = app.open(placeFile) // one of them
  app.activeDocument.selection.selectAll()
  app.activeDocument.selection.copy()
  app.activeDocument.close(SaveOptions.DONOTSAVECHANGES)
  app.activeDocument.paste()
}
