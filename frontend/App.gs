// ====================================================================
// ROJGAARRECORD - MASTER APP ROUTER
// ====================================================================

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('RojgaarRecord ERP')
      .addItem('Open Sidebar', 'openMasterSidebar')
      .addToUi();
}

function openMasterSidebar() {
  const template = HtmlService.createTemplateFromFile('MasterSidebar');
  template.SCRIPT_URL = ScriptApp.getService().getUrl();
  const html = template.evaluate()
      .setTitle('RojgaarRecord ERP')
      .setWidth(400);
  SpreadsheetApp.getUi().showSidebar(html);
}

// --- SESSION MANAGEMENT ---

function getAuthData() {
  const props = PropertiesService.getDocumentProperties();
  return { id: props.getProperty("user_id"), token: props.getProperty("session_token") };
}

function setAuthData(id, token) {
  const props = PropertiesService.getDocumentProperties();
  props.setProperty("user_id", id);
  props.setProperty("session_token", token);
}

function clearAuthData() {
  const props = PropertiesService.getDocumentProperties();
  props.deleteProperty("user_id");
  props.deleteProperty("session_token");
  
  // Wipe the Live_Dashboard screen for security when logging out
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Live_Dashboard");
  if (sheet) {
    sheet.clear();
    sheet.clearFormats();
    sheet.getRange("A1").setValue("SESSION TERMINATED. PLEASE LOGIN.")
         .setFontSize(16).setFontColor("#dc2626").setFontWeight("bold");
  }
}
