// ====================================================================
// ROJGAARRECORD - DYNAMIC VIEW ENGINE (ERP DISPLAY)
// ====================================================================

function renderToDashboard(title, headers, dataRows, chartConfig = null) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName("Live_Dashboard");
  
  if (!sheet) {
    sheet = ss.insertSheet("Live_Dashboard");
  }
  
  sheet.clearContents();
  sheet.getRange(1, 1, 100, 20).setBackground("#ffffff"); // Brutalist background
  
  // 1. Wipe previous data and remove protections/charts/bandings to reset canvas
  const bandings = sheet.getBandings();
  for (let i = 0; i < bandings.length; i++) {
    bandings[i].remove();
  }
  
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET);
  for (let i = 0; i < protections.length; i++) {
    protections[i].remove();
  }
  const charts = sheet.getCharts();
  for (let i = 0; i < charts.length; i++) {
    sheet.removeChart(charts[i]);
  }

  // 2. Set Brutalist Header
  sheet.getRange("A1").setValue(title.toUpperCase())
       .setFontSize(24)
       .setFontWeight("bold")
       .setFontColor("#000000") // Solid Black
       .setVerticalAlignment("middle");
  sheet.getRange("A1:G2").merge(); // Merge to make room for big header
  
  // 3. Render Table Headers
  if (headers && headers.length > 0) {
    const headerRange = sheet.getRange(4, 1, 1, headers.length);
    headerRange.setValues([headers])
               .setFontWeight("bold")
               .setBackground("#000000") // Solid Black Header
               .setFontColor("#ffffff")
               .setHorizontalAlignment("center");
    sheet.setFrozenRows(4); // Freeze headers
  }

  // 4. Render Data Rows
  if (dataRows && dataRows.length > 0 && headers.length > 0) {
    const dataRange = sheet.getRange(5, 1, dataRows.length, headers.length);
    dataRange.setValues(dataRows)
             .setVerticalAlignment("middle")
             .setHorizontalAlignment("center");
             
    // Apply Banding (Alternating colors)
    try {
      const banding = dataRange.applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY, false, false);
    } catch (e) {
      console.warn("Banding skipped: " + e.toString());
    }
  } else if (headers && headers.length > 0) {
    sheet.getRange(5, 1).setValue("No data available for this view.")
         .setFontStyle("italic")
         .setFontColor("#000000");
  }

  // Auto-resize columns for a professional look
  if (headers && headers.length > 0) {
    for (let i = 1; i <= headers.length; i++) {
      sheet.autoResizeColumn(i);
      // Give a little extra padding
      const width = sheet.getColumnWidth(i);
      sheet.setColumnWidth(i, width + 30);
    }
  }

  // 5. Draw Charts (if any)
  if (chartConfig) {
    // chartConfig: { type: 'pie', title: '...', data: [['Label', 'Value'], ['A', 10], ['B', 20]] }
    const tempRange = sheet.getRange(100, 1, chartConfig.data.length, 2);
    tempRange.setValues(chartConfig.data);
    
    const chartBuilder = sheet.newChart()
       .setChartType(chartConfig.type === 'pie' ? Charts.ChartType.PIE : Charts.ChartType.COLUMN)
       .addRange(tempRange)
       .setPosition(6, 1, 0, 0)
       .setOption('title', chartConfig.title)
       .setOption('width', 600)
       .setOption('height', 400);
       
    sheet.insertChart(chartBuilder.build());
    // Hide the temp data by changing text color to white
    tempRange.setFontColor("#ffffff");
  }

  // Removed sheet protection to prevent PERMISSION_DENIED errors in V8 google.script.run context
  
  // Bring sheet to front
  ss.setActiveSheet(sheet);
}

function formatDateDMY(val) {
  if (!val || val === "-") return "-";
  let d = new Date(Number(val));
  if (isNaN(d.getTime())) d = new Date(val);
  if (isNaN(d.getTime())) return val.toString();
  let day = String(d.getDate()).padStart(2, '0');
  let month = String(d.getMonth() + 1).padStart(2, '0');
  let year = String(d.getFullYear()).substring(2);
  return `${day}-${month}-${year}`;
}

// -------------------------------------------------------------
// CONTROLLER ROUTER
// -------------------------------------------------------------

function loadDashboardView(role, id, token, viewName) {
  // Validate Session
  if (role !== "admin") {
    if (!checkActiveSession(id, token)) {
      throw new Error("Invalid Session. Please log in again.");
    }
  }

  const data = fetchUserData(role, id);
  let title = "System Overview";
  let headers = [];
  let rows = [];
  let chartConfig = null;

  // ROUTING LOGIC
  if (viewName === "attendance") {
    title = `Attendance History (${id})`;
    headers = ["Date", "Site ID", "Status", "Hours"];
    data.attendance.forEach(a => rows.push([formatDateDMY(a.dt || a.timestamp), a.siteId, a.status, a.hours || "-"]));
  }
  else if (viewName === "claims") {
    title = `Claims Pipeline (${id})`;
    headers = ["Claim ID", "Contractor", "Type", "Amount", "Status"];
    data.claims.forEach(c => rows.push([c.id, c.contractorId, c.claimType, "₹"+c.amount, c.status]));
  }
  else if (viewName === "active_workers") {
    title = "Active Site Roster";
    headers = ["Worker ID", "Name", "Site ID", "Clock In", "Status"];
    const sites = data.sites.map(s => s.id);
    // Build worker name lookup
    const wrkNameMap = {};
    (data.workers || []).forEach(w => { wrkNameMap[w.id ? w.id.toString().trim() : ""] = w.name || "---"; });
    // Show only Checked In records (active shifts)
    const recentAtt = data.attendance.filter(a => sites.includes(a.siteId) && a.status === "Checked In");
    recentAtt.forEach(a => rows.push([a.workerId, wrkNameMap[a.workerId ? a.workerId.toString().trim() : ""] || "---", a.siteId, a.clockIn || formatDateDMY(a.dt || a.timestamp), a.status]));
  }
  else if (viewName === "accounts") {
    title = "Accounts & Payments";
    headers = ["Worker ID", "Site ID", "Date", "Amount Settled"];
    data.payments.forEach(p => rows.push([p.wrk || p.workerId, p.sid || p.siteId, p.dt ? p.dt.toString() : formatDateDMY(p.dt), "Rs."+p.amount]));
  }
  else if (viewName === "history") {
    title = "Work History Log";
    headers = ["Worker ID", "Date", "Clock In", "Clock Out", "Hours", "Status"];
    const sites = data.sites.map(s => s.id);
    data.attendance.filter(a => sites.includes(a.siteId)).forEach(a => rows.push([a.workerId, a.dt ? a.dt.toString() : formatDateDMY(a.timestamp), a.clockIn || "-", a.clockOut || "-", a.hours || "-", a.status]));
  }
  else if (viewName === "sites") {
    title = "Site Operations Overview";
    headers = ["Site ID", "Name", "Location", "Contractor ID", "Status"];
    data.sites.forEach(s => rows.push([s.id, s.name, s.location, s.contractorId || "UNASSIGNED", s.status]));
  }
  else if (viewName === "daily_ops") {
    title = "Daily Attendance Log";
    headers = ["Site ID", "Worker ID", "Status", "Date"];
    data.attendance.forEach(a => rows.push([a.siteId, a.workerId, a.status, formatDateDMY(a.dt || a.timestamp)]));
  }
  else if (viewName === "overview" && role === "admin") {
    title = "Global Platform Telemetry";
    headers = ["Metric", "Count"];
    rows = [
      ["Total Registered Workers", data.workers.length],
      ["Total Active Contractors", data.contractors.length],
      ["Total Operational Sites", data.sites.length],
      ["Gross Payments Processed", "₹" + data.payments.reduce((acc, p) => acc + (Number(p.amount) || 0), 0)]
    ];
    chartConfig = {
      type: "pie",
      title: "User Demographics",
      data: [
        ["Role", "Count"],
        ["Workers", data.workers.length],
        ["Contractors", data.contractors.length],
        ["Employers", data.employers.length]
      ]
    };
  }
  else if (viewName === "disputes" && role === "admin") {
    title = "Claims & Disputes Telemetry";
    headers = ["Claim ID", "Worker", "Contractor", "Amount", "Status"];
    data.claims.forEach(c => rows.push([c.id, c.workerId, c.contractorId, "₹"+c.amount, c.status]));
    
    let resolved = data.claims.filter(c => c.status.includes("RESOLVED")).length;
    let pending = data.claims.length - resolved;
    chartConfig = {
      type: "pie",
      title: "Claims Resolution Matrix",
      data: [
        ["Status", "Count"],
        ["Resolved", resolved],
        ["Active/Pending", pending]
      ]
    };
  }

  renderToDashboard(title, headers, rows, chartConfig);
}
