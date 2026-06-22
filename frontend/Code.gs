const WEBHOOKS = {
  "db-crud": "https://discord.com/api/webhooks/1517431622511755364/xLUpJaqwSy2sg3GqbH7YKqys7b7Q2jDcWRILafiHIaOs95rbdh7KWKjK2H4bzIMTwT6p",
  "tx-claims": "https://discord.com/api/webhooks/1515360449284280393/6dNEf-JmbGZVBrn3ehOHLJD-DNqtcw5A0GFBjvAMCk-bhzm5iy82OIt68IVxdxixFTD_",
  "tx-payments": "https://discord.com/api/webhooks/1515360462114525257/cKPKKMWp1cs9PTgaJO2PLWdYMdHI--BkK85yzeYDmX8Ohgz8Rcyj6hRkRJnzTGNziuqq",
  "tx-eod-signoffs": "https://discord.com/api/webhooks/1515360468515160147/xYagJ1dNhuOxXTMyve13XUP9vTh3QU4sZ4jxKrHSeJo-uSKKM0AktDrU3ek02ofdr62i",
  "tx-attendance-in": "https://discord.com/api/webhooks/1515709837273600103/3wmdIE-AMNo6dW0H7uUD4L6YB9wTonOsqWJF8wAM-MxPNtgKveAwVVuezt47UqLAAnQU",
  "tx-attendance-out": "https://discord.com/api/webhooks/1515709843967578163/U4o5ACVLC1iQEuvLC1IQJ4RpOu5c28PQdNfGiSo-IUOtyMLZlrZL2_y3_oAFGAiYsYhW",
  "tx-site-registrations": "https://discord.com/api/webhooks/1515709851894808759/KqVEmKoZMnR-YUShCqUqmVvlTYCy2wuG9PW5sFRVhnv85tQTTME-oNCgL2AwD8BReex6",
  "tx-contract-awards": "https://discord.com/api/webhooks/1515709858756825208/j8KbRBipcI9vAOPCCZkpZR_6G-x_rQYa3bEhB-OOuy7ro6xWVaGmbVQ3CIidTYAc4Rpc",
  "tx-claim-resolutions": "https://discord.com/api/webhooks/1515709881267781652/eegi8kuCKVMcAeAw6E1kn9HkzdKsaw_X3YtMCIuJHtbodXG-fpA2pT3X1HlA8lCdby8l",
  "tx-otps": "https://discord.com/api/webhooks/1517431644452032582/J7QHrGHeIQDooCOk0dqU3Ka0sC0jjojDUUqwaPjGAmKgNRTFuMktSVkkWH3bUUxPyrUk"
};

function sendToDiscord(payload) {
  const sheet = payload.sheet;
  const record = payload.record || {};
  const action = payload.action;
  const pid = payload.pid;
  
  if (action === "wipe_all") {
    postPayloadToWebhook(payload, WEBHOOKS["db-crud"]);
    return;
  }
  
  if (sheet === "Sites" && action === "create") {
    // 1. Send DB payload to db-crud for database ledger onboarding
    const dbPayload = {
      action: "create",
      sheet: "Sites",
      pid: pid || record.id || record.sid,
      record: {
        id: record.id || record.sid || pid,
        name: record.name,
        location: record.location,
        size: record.size,
        status: record.status || "Active",
        employer: record.employer || record.emp,
        dt: record.dt || getDDMMYY()
      }
    };
    postPayloadToWebhook(dbPayload, WEBHOOKS["db-crud"]);
    
    // 2. Send Blockchain payload to tx-site-registrations for immutable ledger onboarding
    const txPayload = {
      action: "create",
      sheet: "Sites",
      pid: pid || record.id || record.sid,
      record: {
        emp: record.employer || record.emp,
        sid: record.id || record.sid || pid,
        dt: record.dt || getDDMMYY()
      }
    };
    postPayloadToWebhook(txPayload, WEBHOOKS["tx-site-registrations"]);
    return;
  }
  
  // For other sheets, route properly
  let webhookUrl = WEBHOOKS["db-crud"];
  let cleanRecord = {};
  
  if (sheet === "OTPs") {
    webhookUrl = WEBHOOKS["tx-otps"];
    cleanRecord = record;
  } else if (sheet === "Attendance") {
    if (record.status === "Checked In") {
      webhookUrl = WEBHOOKS["tx-attendance-in"];
      cleanRecord = {
        wrk: record.workerId || record.wrk,
        con: record.contractorId || record.con,
        sid: record.siteId || record.sid,
        dt: record.dt || getDDMMYY()
      };
    } else {
      webhookUrl = WEBHOOKS["tx-attendance-out"];
      cleanRecord = {
        wrk: record.workerId || record.wrk,
        sid: record.siteId || record.sid,
        hours: parseInt(record.hours) || 8,
        dt: record.dt || getDDMMYY()
      };
    }
  } else if (sheet === "Payments") {
    webhookUrl = WEBHOOKS["tx-payments"];
    cleanRecord = {
      type: "payment",
      wrk: record.workerId || record.wrk,
      sid: record.siteId || record.sid,
      amount: parseInt(record.amount) || 0,
      dt: record.dt || getDDMMYY()
    };
  } else if (sheet === "Claims") {
    if (action === "update") {
      webhookUrl = WEBHOOKS["tx-claim-resolutions"];
      cleanRecord = {
        claim_id: record.claim_id || record.id || pid,
        action: "RESOLVED",
        resp_by: record.resp_by || record.con,
        dt: record.dt || getDDMMYY()
      };
    } else {
      webhookUrl = WEBHOOKS["tx-claims"];
      cleanRecord = {
        type: "claim",
        wrk: record.workerId || record.wrk,
        con: record.contractorId || record.con,
        status: "PENDING",
        dt: record.dt || getDDMMYY()
      };
    }
  } else if (sheet === "Sites" && action === "update") {
    webhookUrl = WEBHOOKS["tx-contract-awards"];
    cleanRecord = {
      emp: record.employer || record.emp,
      con: record.contractorId || record.con,
      sid: record.id || record.sid || pid,
      dt: record.dt || getDDMMYY()
    };
  } else if (sheet === "EODSignoffs") {
    webhookUrl = WEBHOOKS["tx-eod-signoffs"];
    cleanRecord = {
      con: record.contractorId || record.con,
      sid: record.siteId || record.sid,
      dt: record.dt || getDDMMYY()
    };
  } else {
    // Workers, Contractors, Employers (DB registries)
    webhookUrl = WEBHOOKS["db-crud"];
    cleanRecord = record;
  }
  
  const cleanPayload = {
    action: action,
    sheet: sheet,
    record: cleanRecord
  };
  if (pid !== undefined) cleanPayload.pid = pid;
  
  postPayloadToWebhook(cleanPayload, webhookUrl);
}

function postPayloadToWebhook(payload, webhookUrl) {
  let color = 3447003; // Blue for update
  let title = "Ledger Update";
  if (payload.action === "create") { color = 3066993; title = "New Ledger Entry"; }
  else if (payload.action === "delete") { color = 15158332; title = "Ledger Deletion"; }
  
  let actStr = payload.action ? payload.action.toUpperCase() : "UPDATE";
  let desc = `Action: **${actStr}**\nSheet: **${payload.sheet}**\nPID: **${payload.pid || 'N/A'}**\n\n`;
  desc += `\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\``;

  const discordPayload = {
    embeds: [{
      title: title,
      color: color,
      description: desc,
      timestamp: new Date().toISOString()
    }]
  };

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(discordPayload),
    muteHttpExceptions: true
  };
  try {
    UrlFetchApp.fetch(webhookUrl, options);
  } catch (err) {
    console.error("Discord webhook attempt failed: " + err.toString());
  }
}

// Helper to get or create sheet with headers
function getOrCreateSheet(sheetName, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
    sheet.appendRow(headers);
  }
  return sheet;
}

// Find phone number for a user
function isIdHeader(h) {
  if (!h) return false;
  const lower = h.toString().trim().toLowerCase();
  return lower === "id" || lower === "pid" || lower === "workerid" || lower === "contractorid" || lower === "employerid" || lower === "siteid";
}

function findPhoneInSheet(sheetName, id) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet) return "";
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return "";
  const headers = data[0].map(function(h) { return h.toString().trim().toLowerCase(); });
  
  let idIdx = -1;
  for (let j = 0; j < headers.length; j++) {
    if (isIdHeader(headers[j])) {
      idIdx = j;
      break;
    }
  }
  const phoneIdx = headers.indexOf('phone');
  if (idIdx === -1 || phoneIdx === -1) return "";
  for (let i = 1; i < data.length; i++) {
    const rowId = data[i][idIdx] ? data[i][idIdx].toString().trim().toUpperCase() : "";
    if (rowId === id.toString().trim().toUpperCase()) {
      return data[i][phoneIdx];
    }
  }
  return "";
}

function getRecordFieldValue(sheetName, id, fieldName) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet) return "";
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return "";
  const headers = data[0].map(h => h.toString().trim().toLowerCase());
  let idIdx = -1;
  for (let j = 0; j < headers.length; j++) {
    if (isIdHeader(headers[j])) {
      idIdx = j;
      break;
    }
  }
  if (idIdx === -1) idIdx = 0;
  const fieldIdx = headers.indexOf(fieldName.toLowerCase());
  if (fieldIdx === -1) return "";
  for (let i = 1; i < data.length; i++) {
    if (data[i][idIdx] && data[i][idIdx].toString().trim().toUpperCase() === id.toString().trim().toUpperCase()) {
      return data[i][fieldIdx];
    }
  }
  return "";
}

function recordExists(sheetName, id) {
  if (!id) return false;
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet) return false;
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return false;
  const headers = data[0].map(h => h.toString().trim().toLowerCase());
  let idIdx = -1;
  for (let j = 0; j < headers.length; j++) {
    if (isIdHeader(headers[j])) {
      idIdx = j;
      break;
    }
  }
  if (idIdx === -1) idIdx = 0;
  for (let i = 1; i < data.length; i++) {
    if (data[i][idIdx] && data[i][idIdx].toString().trim() === id.toString().trim()) {
      return true;
    }
  }
  return false;
}

// Modular SMS dispatch - simulated via Discord
function sendSMS(phone, message) {
  console.log(`[SMS Gateway] Sending to ${phone}: ${message}`);
  
  const discordPayload = {
    embeds: [{
      title: "📡 Simulated SMS Gateway Dispatch",
      color: 4616690, // Stark Dark Blue for corporate brutalism
      description: `**To (Registered Phone)**: \`${phone}\`\n**Message**: ${message}`,
      timestamp: new Date().toISOString()
    }]
  };
  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(discordPayload),
    muteHttpExceptions: true
  };
  try {
    UrlFetchApp.fetch(WEBHOOKS["tx-otps"], options);
  } catch (err) {
    console.error("SMS notification attempt failed: " + err.toString());
  }
}

// Validate if session token is active and not expired
function checkActiveSession(id, token) {
  if (!id || !token) return false;
  if (id === "ADMIN" && token === "ADMIN_TOKEN") return true; // Quick fallback
  const sheet = getOrCreateSheet("Sessions", ["id", "session_token", "last_active_time"]);
  const data = sheet.getDataRange().getValues();
  
  for (let i = 1; i < data.length; i++) {
    const rowId = data[i][0] ? data[i][0].toString().trim() : "";
    const rowToken = data[i][1] ? data[i][1].toString().trim() : "";
    if (rowId === id.toString().trim()) {
      if (rowToken === token.toString().trim()) {
        // Update last_active_time as raw epoch ms (no apostrophe prefix)
        sheet.getRange(i + 1, 3).setValue(Date.now());
        return true;
      }
      return false; // Token mismatch
    }
  }
  return false;
}

function getDDMMYY() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}-${mm}-${yy}`;
}

// Helper to get all data from a sheet as JSON array
function getSheetData(sheetName, ss) {
  const activeSs = ss || SpreadsheetApp.getActiveSpreadsheet();
  const sheet = activeSs.getSheetByName(sheetName);
  if (!sheet) return [];
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  let results = [];
  for(let i=1; i<data.length; i++) {
    let rowObj = {};
    for(let j=0; j<headers.length; j++) {
      let key = headers[j] ? headers[j].toString().trim() : "";
      if (key.toLowerCase() === "pid") key = "id";
      rowObj[key] = data[i][j];
    }
    results.push(rowObj);
  }
  return results;
}

// Fetch all role-filtered tables
function fetchUserData(role, id) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let responseData = {
     workers: [],
     contractors: [],
     employers: [],
     sites: [],
     attendance: [],
     payments: [],
     claims: []
  };

  if (role === "admin") {
     responseData.workers = getSheetData("Workers", ss);
     responseData.contractors = getSheetData("Contractors", ss);
     responseData.employers = getSheetData("Employers", ss);
     responseData.sites = getSheetData("Sites", ss);
     responseData.attendance = getSheetData("Attendance", ss);
     responseData.payments = getSheetData("Payments", ss);
     responseData.claims = getSheetData("Claims", ss);
     responseData.sessions = getSheetData("Sessions", ss);
     responseData.otps = getSheetData("PendingOTPs", ss);
  } else if (role === "worker") {
     responseData.workers = getSheetData("Workers", ss).filter(r => r.id && r.id.toString().trim() === id);
     responseData.attendance = getSheetData("Attendance", ss).filter(r => r.workerId && r.workerId.toString().trim() === id);
     responseData.payments = getSheetData("Payments", ss).filter(r => r.workerId && r.workerId.toString().trim() === id);
     responseData.claims = getSheetData("Claims", ss).filter(r => r.workerId && r.workerId.toString().trim() === id);
     const allSites = getSheetData("Sites", ss);
     const attendedSiteIds = responseData.attendance.map(a => a.siteId ? a.siteId.toString().trim() : "");
     responseData.sites = allSites.filter(s => s.id && attendedSiteIds.includes(s.id.toString().trim()));
  } else if (role === "contractor") {
     responseData.contractors = getSheetData("Contractors", ss).filter(r => r.id && r.id.toString().trim() === id);
     responseData.sites = getSheetData("Sites", ss).filter(r => r.contractorId && r.contractorId.toString().trim() === id);
     const siteIds = responseData.sites.map(s => s.id ? s.id.toString().trim() : "");
     responseData.attendance = getSheetData("Attendance", ss).filter(r => r.siteId && siteIds.indexOf(r.siteId.toString().trim()) !== -1);
     const workerIdsOnSite = [...new Set(responseData.attendance.map(a => a.workerId ? a.workerId.toString().trim() : "").filter(Boolean))];
     responseData.workers = getSheetData("Workers", ss).filter(r => r.id && workerIdsOnSite.indexOf(r.id.toString().trim()) !== -1);
     responseData.payments = getSheetData("Payments", ss).filter(r => r.siteId && siteIds.indexOf(r.siteId.toString().trim()) !== -1);
     responseData.claims = getSheetData("Claims", ss).filter(r => r.contractorId && r.contractorId.toString().trim() === id);
  } else if (role === "employer") {
     responseData.employers = getSheetData("Employers", ss).filter(r => r.id && r.id.toString().trim() === id);
     responseData.sites = getSheetData("Sites", ss).filter(r => r.employer && r.employer.toString().trim() === id);
     // Employers can view attendance for workers at their sites
     const siteIds = responseData.sites.map(s => s.id ? s.id.toString().trim() : "");
     responseData.attendance = getSheetData("Attendance", ss).filter(r => r.siteId && siteIds.indexOf(r.siteId.toString().trim()) !== -1);
     responseData.claims = getSheetData("Claims", ss).filter(r => r.siteId && siteIds.indexOf(r.siteId.toString().trim()) !== -1);
     // Exclude Payments as payments are strictly private between contractor and worker
  }
  return responseData;
}

// GET Endpoint for SPA DB Fetch
function doGet(e) {
  const role = e.parameter.role || ""; 
  const id = e.parameter.id || ""; 
  const token = e.parameter.token || "";
  const action = e.parameter.action || "";

  try {
    // 1. Session check validation action
    if (action === "validate_session") {
      const isValid = checkActiveSession(id, token);
      return ContentService.createTextOutput(JSON.stringify({valid: isValid})).setMimeType(ContentService.MimeType.JSON);
    }

    // 2. Regular data read authorization
    if (role !== "admin" && role !== "") {
      if (!checkActiveSession(id, token)) {
        return ContentService.createTextOutput(JSON.stringify({error: "Session expired or invalid. Please login again."})).setMimeType(ContentService.MimeType.JSON);
      }
    }

    const responseData = fetchUserData(role, id);
    return ContentService.createTextOutput(JSON.stringify(responseData)).setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService.createTextOutput(JSON.stringify({error: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

// POST Endpoint for DB Operations & Auth Actions
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const action = payload.action; 
    const sheetName = payload.sheet; 
    let pid = payload.pid;
    let record = payload.record || {};
    
    // Format dates to dd-mm-yy and stringify phone immediately so all downstreams (Sheets, Discord, Ledger) get standard format
    if (record.dt) record.dt = formatDateDMY(record.dt);
    if (record.dob) record.dob = formatDateDMY(record.dob);
    if (record.phone !== undefined && record.phone !== null) {
      record.phone = record.phone.toString().trim();
    }
    
    // =====================================
    // END-TO-END WIPE ACTIONS
    // =====================================
    if (action === "wipe_all") {
      const sheetsToClear = ["Workers", "Contractors", "Employers", "Sites", "Contracts", "Attendance", "Claims", "Payments", "PendingOTPs", "Sessions", "EODSignoffs", "Live_Dashboard"];
      sheetsToClear.forEach(name => {
        const s = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
        if (s) {
          const lastRow = s.getLastRow();
          if (lastRow > 1) {
            s.getRange(2, 1, lastRow - 1, s.getLastColumn()).clearContent();
          }
        }
      });
      sendToDiscord({ action: "wipe_all", sheet: "SYSTEM", pid: "WIPE" });
      return ContentService.createTextOutput(JSON.stringify({ok: true})).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (action === "load_dashboard_view") {
      loadDashboardView(payload.authRole, payload.authId, payload.authToken, payload.viewName);
      return ContentService.createTextOutput(JSON.stringify({ok: true})).setMimeType(ContentService.MimeType.JSON);
    }

    // =====================================
    // AUTHENTICATION & LOGIN ACTIONS
    // =====================================
    
    if (action === "generate_payment_otp") {
      const workerId = payload.workerId ? payload.workerId.toString().trim().toUpperCase() : "";
      const phone = findPhoneInSheet("Workers", workerId);
      if (!phone) return ContentService.createTextOutput(JSON.stringify({error: "Worker phone not found."})).setMimeType(ContentService.MimeType.JSON);
      
      const otp = Math.floor(1000 + Math.random() * 9000).toString();
      const pendingSheet = getOrCreateSheet("PendingOTPs", ["id", "otp", "timestamp", "phone"]);
      // Delete any existing pay-OTP for this worker first — only ONE valid OTP at a time
      const pendingExisting = pendingSheet.getDataRange().getValues();
      for (let i = pendingExisting.length - 1; i >= 1; i--) {
        const rowId = pendingExisting[i][0] ? pendingExisting[i][0].toString().trim().toUpperCase() : "";
        if (rowId === workerId + "-PAY") pendingSheet.deleteRow(i + 1);
      }
      pendingSheet.appendRow([workerId + "-PAY", otp, Date.now(), phone]);
      
      const authId = payload.authId ? payload.authId.toString().trim().toUpperCase() : "";
      const conName = getRecordFieldValue("Contractors", authId, "name") || "Contractor";
      const siteName = getRecordFieldValue("Sites", payload.siteId, "name") || "Site";
      const msgText = `${conName} is paying you Rs.${payload.amount} for ${siteName} on ${getDDMMYY()}. OTP: ${otp}`;
      sendSMS(phone, msgText);
      
      const maskedPhone = phone.toString().substring(0, 3) + "****" + phone.toString().substring(7);
      return ContentService.createTextOutput(JSON.stringify({ok: true, maskedPhone: maskedPhone})).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (action === "verify_payment_otp") {
      const workerId = payload.workerId ? payload.workerId.toString().trim().toUpperCase() : "";
      const otp = payload.otp;
      const pendingSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("PendingOTPs");
      if (!pendingSheet) return ContentService.createTextOutput(JSON.stringify({error: "OTP system error."})).setMimeType(ContentService.MimeType.JSON);
      
      const otpData = pendingSheet.getDataRange().getValues();
      let isValid = false;
      let rowIndex = -1;
      const nowMs = new Date().getTime();
      
      for (let i = 1; i < otpData.length; i++) {
        const rowId = otpData[i][0] ? otpData[i][0].toString().trim().toUpperCase() : "";
        if (rowId === workerId + "-PAY" && otpData[i][1].toString() === otp.toString()) {
          let tsVal = otpData[i][2];
          let ts = NaN;
          if (tsVal instanceof Date) ts = tsVal.getTime();
          else if (tsVal) ts = Number(tsVal.toString().replace(/['\s]/g, ''));
          if (!isNaN(ts) && Math.abs(nowMs - ts) < 5 * 60 * 1000) {
            isValid = true;
            rowIndex = i + 1;
            break;
          }
        }
      }
      
      if (!isValid) return ContentService.createTextOutput(JSON.stringify({error: "Invalid or expired OTP."})).setMimeType(ContentService.MimeType.JSON);
      
      pendingSheet.deleteRow(rowIndex);
      
      // Calculate hours from check-in time
      const siteId = payload.siteId ? payload.siteId.toString().trim().toUpperCase() : "";
      const attSheet = getOrCreateSheet("Attendance", ["workerId", "siteId", "dt", "clockIn", "clockOut", "status", "hours"]);
      const attData = attSheet.getDataRange().getValues();
      const attHdrs = attData[0].map(h => h.toString().trim().toLowerCase());
      const attWrkIdx = attHdrs.indexOf("workerid");
      const attSiteIdx = attHdrs.indexOf("siteid");
      const attStatusIdx = attHdrs.indexOf("status");
      const attClockInIdx = attHdrs.indexOf("clockin");
      let checkInTimeStr = "";
      let checkInRowIdx = -1;
      // Find the most recent Check-In row for this worker+site
      for (let i = attData.length - 1; i >= 1; i--) {
        const rWrk = attData[i][attWrkIdx] ? attData[i][attWrkIdx].toString().trim().toUpperCase() : "";
        const rSite = attData[i][attSiteIdx] ? attData[i][attSiteIdx].toString().trim().toUpperCase() : "";
        const rStatus = attData[i][attStatusIdx] ? attData[i][attStatusIdx].toString().trim() : "";
        if (rWrk === workerId && rSite === siteId && rStatus === "Checked In") {
          checkInTimeStr = attClockInIdx !== -1 ? attData[i][attClockInIdx].toString().trim() : "";
          checkInRowIdx = i;
          break;
        }
      }
      
      // Compute hours from check-in to now
      const nowTime = new Date();
      const clockOutStr = String(nowTime.getHours()).padStart(2,'0') + ":" + String(nowTime.getMinutes()).padStart(2,'0');
      let hoursWorked = payload.hours || 8;
      if (checkInTimeStr) {
        const parts = checkInTimeStr.split(":");
        if (parts.length === 2) {
          const inMs = (parseInt(parts[0]) * 60 + parseInt(parts[1])) * 60 * 1000;
          const outMs = (nowTime.getHours() * 60 + nowTime.getMinutes()) * 60 * 1000;
          const diffMs = outMs - inMs;
          hoursWorked = diffMs > 0 ? Math.round((diffMs / 3600000) * 10) / 10 : (payload.hours || 8);
        }
      }
      const dateStr = getDDMMYY();
      
      attSheet.appendRow([workerId, siteId, dateStr, checkInTimeStr, clockOutStr, "Checked Out", hoursWorked]);
      // Blockchain tx-attendance-out: wrk, sid, hours, dt (DD-MM-YY)
      sendToDiscord({sheet: "Attendance", record: {workerId: workerId, wrk: workerId, siteId: siteId, sid: siteId, status: "Checked Out", hours: hoursWorked, clockOut: clockOutStr, dt: dateStr}});
      
      // Resolve empId from Sites sheet
      const sitesSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sites");
      let empId = "";
      if (sitesSheet) {
        const sitesData = sitesSheet.getDataRange().getValues();
        const sHdrs = sitesData[0].map(h => h.toString().trim().toLowerCase());
        const empIdx = sHdrs.indexOf("employer") !== -1 ? sHdrs.indexOf("employer") : sHdrs.indexOf("emp");
        for (let i = 1; i < sitesData.length; i++) {
          if (sitesData[i][0] && sitesData[i][0].toString().trim().toUpperCase() === siteId) {
            if (empIdx !== -1) empId = sitesData[i][empIdx];
            break;
          }
        }
      }
      
      const paySheet = getOrCreateSheet("Payments", ["type", "workerId", "siteId", "amount", "dt", "employerId"]);
      paySheet.appendRow(["WAGE", workerId, siteId, payload.amount, dateStr, empId]);
      sendToDiscord({sheet: "Payments", record: {type: "payment", workerId: workerId, wrk: workerId, siteId: siteId, sid: siteId, amount: payload.amount, dt: dateStr}});
      
      return ContentService.createTextOutput(JSON.stringify({ok: true})).setMimeType(ContentService.MimeType.JSON);
    }

    if (action === "request_otp") {
      const id = payload.id ? payload.id.toString().trim().toUpperCase() : "";
      let phone = "";
      if (id.startsWith("WRK-")) phone = findPhoneInSheet("Workers", id);
      else if (id.startsWith("CON-")) phone = findPhoneInSheet("Contractors", id);
      else if (id.startsWith("EMP-")) phone = findPhoneInSheet("Employers", id);
      
      if (!phone) {
        return ContentService.createTextOutput(JSON.stringify({error: "User ID not found in Registry."})).setMimeType(ContentService.MimeType.JSON);
      }
      
      // OTP always generated upon request
      
      // Generate OTP — only ONE valid OTP per user at a time
      const otp = Math.floor(1000 + Math.random() * 9000).toString();
      const pendingSheet = getOrCreateSheet("PendingOTPs", ["id", "otp", "timestamp", "phone"]);
      
      // Delete ALL existing OTPs for this ID before inserting new one
      const pendingData = pendingSheet.getDataRange().getValues();
      for (let i = pendingData.length - 1; i >= 1; i--) {
        const rowId = pendingData[i][0] ? pendingData[i][0].toString().trim().toUpperCase() : "";
        if (rowId === id) {
          pendingSheet.deleteRow(i + 1);
        }
      }
      
      // Store raw epoch ms — no apostrophe prefix so Number() parsing always works
      pendingSheet.appendRow([id, otp, Date.now(), phone]);
      sendSMS(phone, `RojgaarRecord Security OTP: ${otp}. Valid for 5 minutes.`);
      
      const maskedPhone = phone.toString().substring(0, 3) + "****" + phone.toString().substring(7);
      return ContentService.createTextOutput(JSON.stringify({ok: true, maskedPhone: maskedPhone})).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (action === "verify_otp") {
      const id = payload.id ? payload.id.toString().trim().toUpperCase() : "";
      const otp = payload.otp;
      const pendingSheet = getOrCreateSheet("PendingOTPs", ["id", "otp", "timestamp", "phone"]);
      const pendingData = pendingSheet.getDataRange().getValues();
      let validOtp = false;
      const now = new Date().getTime();
      
      for (let i = 1; i < pendingData.length; i++) {
        const rowId = pendingData[i][0] ? pendingData[i][0].toString().trim().toUpperCase() : "";
        const rowOtp = pendingData[i][1] ? pendingData[i][1].toString().trim() : "";
        if (rowId === id && rowOtp === otp.toString().trim()) {
          let tsVal = pendingData[i][2];
          let timestamp = NaN;
          if (tsVal instanceof Date) {
            timestamp = tsVal.getTime();
          } else if (tsVal) {
            timestamp = Number(tsVal.toString().replace(/['\s]/g, ''));
          }
          
          if (!isNaN(timestamp) && Math.abs(now - timestamp) < 5 * 60 * 1000) {
            validOtp = true;
            pendingSheet.deleteRow(i + 1);
            break;
          }
        }
      }
      
      if (!validOtp) {
        return ContentService.createTextOutput(JSON.stringify({error: "Invalid or expired OTP."})).setMimeType(ContentService.MimeType.JSON);
      }
      
      // Generate unique token
      const sessionToken = Utilities.getUuid();
      const sessionsSheet = getOrCreateSheet("Sessions", ["id", "session_token", "last_active_time"]);
      const sessionsData = sessionsSheet.getDataRange().getValues();
      
      // Delete any existing sessions for this ID first to keep it clean and only have active ones
      for (let i = sessionsData.length - 1; i >= 1; i--) {
        const rowId = sessionsData[i][0] ? sessionsData[i][0].toString().trim().toUpperCase() : "";
        if (rowId === id) {
          sessionsSheet.deleteRow(i + 1);
        }
      }
      
      // Store raw epoch ms — no apostrophe prefix
      sessionsSheet.appendRow([id, sessionToken, Date.now()]);
      
      let role = "";
      if (id.startsWith("WRK-")) role = "worker";
      else if (id.startsWith("CON-")) role = "contractor";
      else if (id.startsWith("EMP-")) role = "employer";
      
      const userData = fetchUserData(role, id);
      return ContentService.createTextOutput(JSON.stringify({ok: true, token: sessionToken, role: role, data: userData})).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (action === "logout") {
      const id = payload.id ? payload.id.toString().trim().toUpperCase() : "";
      const token = payload.token ? payload.token.toString().trim() : "";
      const sessionsSheet = getOrCreateSheet("Sessions", ["id", "session_token", "last_active_time"]);
      const sessionsData = sessionsSheet.getDataRange().getValues();
      
      // Delete all matching sessions from bottom to top
      for (let i = sessionsData.length - 1; i >= 1; i--) {
        const rowId = sessionsData[i][0] ? sessionsData[i][0].toString().trim().toUpperCase() : "";
        const rowToken = sessionsData[i][1] ? sessionsData[i][1].toString().trim() : "";
        if (rowId === id && (rowToken === token || token === "FORCE")) {
          sessionsSheet.deleteRow(i + 1);
        }
      }
      
      // Wipe the Live_Dashboard screen when logging out
      const liveDashboardSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Live_Dashboard");
      if (liveDashboardSheet) {
        liveDashboardSheet.clear();
        liveDashboardSheet.clearFormats();
        liveDashboardSheet.getRange("A1").setValue("SESSION TERMINATED. PLEASE LOGIN.")
             .setFontSize(16).setFontColor("#dc2626").setFontWeight("bold");
      }
      
      return ContentService.createTextOutput(JSON.stringify({ok: true})).setMimeType(ContentService.MimeType.JSON);
    }
    
    // =====================================
    // CRUD DATA WRITE ACTIONS (SECURED)
    // =====================================
    // Require session check for CRUD updates unless it's user registration
    const isRegistration = (action === "create" && (sheetName === "Workers" || sheetName === "Contractors" || sheetName === "Employers"));
    if (!isRegistration) {
      const authId = payload.authId || "";
      const authToken = payload.authToken || "";
      if (authId !== "admin") {
        if (!checkActiveSession(authId, authToken)) {
          return ContentService.createTextOutput(JSON.stringify({error: "Unauthorized action. Invalid or expired session."})).setMimeType(ContentService.MimeType.JSON);
        }
      }
    }

    // Contractor existence check for Site registration/delegation
    if (sheetName === "Sites" && (action === "create" || action === "update")) {
      const conId = record.contractorId || record.con;
      if (conId && conId !== "UNASSIGNED" && conId.toString().trim() !== "") {
        if (!recordExists("Contractors", conId)) {
          return ContentService.createTextOutput(JSON.stringify({error: "Contractor ID " + conId + " does not exist in registry. Please enter a valid registered Contractor ID."})).setMimeType(ContentService.MimeType.JSON);
        }
      }
    }

    let sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
    const isRegistry = (sheetName === "Workers" || sheetName === "Contractors" || sheetName === "Employers" || sheetName === "Sites" || sheetName === "Claims");
    if (!sheet) {
      if (action === "create") {
        let h = Object.keys(record);
        if (isRegistry) h.unshift("id");
        h.push("Action");
        sheet = getOrCreateSheet(sheetName, h);
      } else {
        return ContentService.createTextOutput(JSON.stringify({error: "Sheet not found"})).setMimeType(ContentService.MimeType.JSON);
      }
    }

    if (action === "create" && isRegistry) {
       const prefix = sheetName === "Workers" ? "WRK" : 
                      sheetName === "Contractors" ? "CON" : 
                      sheetName === "Employers" ? "EMP" : 
                      sheetName === "Sites" ? "SID" : "CLAIM_SUB";
       let usedIds = new Set();
       const dataRange = sheet.getDataRange().getValues();
       if (dataRange.length > 0) {
           const headersList = dataRange[0];
           const idIdx = headersList.indexOf('id');
           if (idIdx !== -1) {
               for(let i=1; i<dataRange.length; i++) {
                  if (dataRange[i][idIdx] && typeof dataRange[i][idIdx] === 'string' && dataRange[i][idIdx].startsWith(prefix)) {
                      let parts = dataRange[i][idIdx].split('-');
                      let parsed = parseInt(parts[parts.length - 1]);
                      if (!isNaN(parsed)) usedIds.add(parsed);
                  }
               }
           }
       }
       
       let nextNum = (sheetName === "Claims") ? 0 : 1;
       while(usedIds.has(nextNum)) {
           nextNum++;
       }
       
       if (sheetName === "Claims") {
           pid = `${prefix}-${nextNum}`;
       } else {
           const num = nextNum.toString().padStart(3, '0');
           pid = `${prefix}-${num}`;
       }
       record.id = pid; 
       payload.pid = pid;
       if (sheetName === "Sites") record.sid = pid;
       if (sheetName === "Claims") record.claim_id = pid;
       payload.record = record;
    }

    if (sheetName === "Attendance" && action === "create") {
      const sitesSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sites");
      if (sitesSheet) {
        const sitesData = sitesSheet.getDataRange().getValues();
        const sHdrs = sitesData[0].map(h => h.toString().trim().toLowerCase());
        const conIdx = sHdrs.indexOf("contractorid");
        for (let i = 1; i < sitesData.length; i++) {
          if (sitesData[i][0] && sitesData[i][0].toString().trim().toUpperCase() === (record.siteId || "").toString().trim().toUpperCase()) {
            if (conIdx !== -1) record.contractorId = sitesData[i][conIdx];
            break;
          }
        }
      }
      // Store clock-in time as HH:MM for hours calculation at clock-out
      const nowIn = new Date();
      const clockInStr = String(nowIn.getHours()).padStart(2,'0') + ":" + String(nowIn.getMinutes()).padStart(2,'0');
      record.status = "Checked In";
      record.dt = getDDMMYY();
      record.clockIn = clockInStr;
      record.timestamp = getDDMMYY();
      record.wrk = record.workerId;
      record.sid = record.siteId;
      record.con = record.contractorId;
    }

    let headers = [];
    if (sheet.getLastColumn() > 0) {
        headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(function(h) { return h.toString().trim(); });
        let headersUpdated = false;
        for (let key in record) {
            if (headers.indexOf(key) === -1 && key !== "Action") {
                const actionIdx = headers.indexOf('Action');
                if (actionIdx !== -1) {
                    headers.splice(actionIdx, 0, key);
                } else {
                    headers.push(key);
                }
                headersUpdated = true;
            }
        }
        if (headersUpdated) {
            sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
        }
    } else {
        headers = Object.keys(record);
        // Ensure 'id' is always the first column
        const idIdx = headers.indexOf('id');
        if (idIdx !== -1) {
            headers.splice(idIdx, 1);
            headers.unshift('id');
        } else if (sheetName !== "PendingOTPs" && sheetName !== "Sessions") {
            headers.unshift('id');
        }
        
        // Ensure 'Action' is the last column
        const actionIdx = headers.indexOf('Action');
        if (actionIdx !== -1) {
            headers.splice(actionIdx, 1);
        }
        headers.push('Action');
        
        sheet.appendRow(headers);
    }

    let rowData = [];
    for (let i = 0; i < headers.length; i++) {
        let key = headers[i];
        if (key === "Action") {
            rowData.push("SYNCED");
        } else {
            rowData.push(record[key] || "");
        }
    }

    if (action === "create") {
      sheet.appendRow(rowData);
    } else if (action === "update") {
      const data = sheet.getDataRange().getValues();
      for(let i=1; i<data.length; i++) {
        if (data[i][0] === pid) {
          // Merge old values for keys that were not provided
          for (let j = 0; j < headers.length; j++) {
            let key = headers[j];
            if (key !== "Action" && record[key] === undefined) {
               record[key] = data[i][j];
               rowData[j] = data[i][j];
            }
          }
          sheet.getRange(i+1, 1, 1, rowData.length).setValues([rowData]);
          break;
        }
      }
    } else if (action === "delete") {
      const data = sheet.getDataRange().getValues();
      for(let i=1; i<data.length; i++) {
        if (data[i][0] === pid) {
          sheet.deleteRow(i+1);
          break;
        }
      }
      if (sheetName === "Employers") {
        deleteAssociatedSites(pid);
      }
    }
    
    sendToDiscord(payload);
    return ContentService.createTextOutput(JSON.stringify({ok: true, pid: pid})).setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService.createTextOutput(JSON.stringify({error: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

// Catch manual edits via custom menu button
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('RojgaarRecord')
      .addItem('Sync Pending Actions', 'syncPendingActions')
      .addToUi();
}

function syncPendingActions() {
  const sheets = ['Workers', 'Contractors', 'Employers', 'Sites'];
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let syncCount = 0;
  
  for (let s of sheets) {
    const sheet = ss.getSheetByName(s);
    if (!sheet) continue;
    
    const data = sheet.getDataRange().getValues();
    if (data.length < 2) continue;
    
    const headers = data[0];
    const actionIdx = headers.indexOf('Action');
    if (actionIdx === -1) continue;
    
    let idIdx = headers.indexOf('id');
    if (idIdx === -1 && headers.indexOf('pid') !== -1) idIdx = headers.indexOf('pid');
    if (idIdx === -1) idIdx = 0;
    
    for (let i = data.length - 1; i >= 1; i--) {
      const action = data[i][actionIdx];
      const pid = data[i][idIdx];
      if (!pid) continue;
      
      let actionUpper = action.toString().toUpperCase().trim();
      if (actionUpper === "") {
        actionUpper = "CREATE"; // Fallback for manual inputs with blank Action
      }
      
      if (actionUpper === "CREATE" || actionUpper === "UPDATE") {
         let record = {};
         for(let j=0; j<headers.length; j++){
            if (j !== actionIdx) record[headers[j]] = data[i][j];
         }
         const payload = { action: actionUpper.toLowerCase(), pid: pid, record: record, sheet: s };
         sendToDiscord(payload);
         sheet.getRange(i + 1, actionIdx + 1).setValue("SYNCED");
         syncCount++;
      } else if (actionUpper === "DELETE") {
         const payload = { action: "delete", pid: pid, sheet: s };
         sendToDiscord(payload);
         sheet.deleteRow(i + 1);
         syncCount++;
      }
    }
  }
  SpreadsheetApp.getUi().alert(`Sync Complete! Successfully processed ${syncCount} pending action(s) to the Ledger.`);
}

// Cascading delete associated sites when an employer is deleted
function deleteAssociatedSites(empId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sitesSheet = ss.getSheetByName("Sites");
  if (!sitesSheet) return;
  
  const data = sitesSheet.getDataRange().getValues();
  if (data.length < 2) return;
  
  const headers = data[0];
  const empIdx = headers.indexOf("employer");
  const idIdx = headers.indexOf("id");
  if (empIdx === -1 || idIdx === -1) return;
  
  // Go from bottom to top to avoid index shifting when deleting rows
  for (let i = data.length - 1; i >= 1; i--) {
    const siteEmployer = data[i][empIdx] ? data[i][empIdx].toString().trim() : "";
    const siteId = data[i][idIdx] ? data[i][idIdx].toString().trim() : "";
    if (siteEmployer === empId.toString().trim() && siteId) {
      // Trigger deletion webhook for the site
      const payload = {
        action: "delete",
        pid: siteId,
        sheet: "Sites"
      };
      sendToDiscord(payload);
      
      // Delete from sheets
      sitesSheet.deleteRow(i + 1);
    }
  }
}

// Format date to dd-mm-yy
function formatDateDMY(val) {
  if (!val) return "";
  let d;
  if (!isNaN(val) && (typeof val === 'number' || !isNaN(parseInt(val)))) {
    d = new Date(Number(val));
  } else {
    d = new Date(val);
  }
  if (isNaN(d.getTime())) {
    const str = val.toString().trim();
    const parts = str.split('-');
    if (parts.length === 3) {
      if (parts[0].length === 4) { // yyyy-mm-dd
        return `${parts[2]}-${parts[1]}-${parts[0].substring(2)}`;
      }
      return str;
    }
    return str;
  }
  let day = String(d.getDate()).padStart(2, '0');
  let month = String(d.getMonth() + 1).padStart(2, '0');
  let year = String(d.getFullYear()).substring(2); // last 2 digits
  return `${day}-${month}-${year}`;
}

// =====================================
// INTERNAL UI BRIDGES (google.script.run)
// =====================================
function processInternalAction(payload) {
  const e = { postData: { contents: JSON.stringify(payload) } };
  const response = doPost(e);
  const result = JSON.parse(response.getContent());
  if (result.error) throw new Error(result.error);
  return result;
}

function apiRequestOTP(id) {
  return processInternalAction({action: "request_otp", id: id});
}

function apiVerifyOTP(id, otp) {
  return processInternalAction({action: "verify_otp", id: id, otp: otp});
}

function apiExecuteAction(payload) {
  return processInternalAction(payload);
}

function fetchUserDataDirect(role, id, token) {
  if (role !== "admin") {
    if (!checkActiveSession(id, token)) {
      throw new Error("Session expired or invalid. Please login again.");
    }
  }
  return fetchUserData(role, id);
}

// Run this manually from the Apps Script editor once if you encounter PERMISSION_DENIED
function forceAuth() {
  PropertiesService.getDocumentProperties().setProperty('auth_test', '1');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName("Live_Dashboard")) ss.insertSheet("Live_Dashboard");
  UrlFetchApp.fetch("https://discord.com/api/webhooks/1517431622511755364/xLUpJaqwSy2sg3GqbH7YKqys7b7Q2jDcWRILafiHIaOs95rbdh7KWKjK2H4bzIMTwT6p", {method: "post", contentType: "application/json", payload: JSON.stringify({content: "Auth OK"}), muteHttpExceptions: true});
}
