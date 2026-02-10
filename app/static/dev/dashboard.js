/**
 * Zwembad.eu AI - Developer Dashboard
 *
 * Dark-themed developer dashboard for feature flag management,
 * system monitoring, and configuration viewing.
 */

var devPassword = null;

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function showToast(message, type) {
    var toast = document.getElementById("toast");
    var inner = toast.querySelector("div");
    inner.textContent = message;
    var colors = {
        success: "bg-green-600",
        error: "bg-red-600",
        warning: "bg-yellow-600",
        info: "bg-blue-600",
    };
    inner.className = "rounded-lg px-4 py-3 shadow-lg text-white text-sm font-medium " + (colors[type] || colors.info);
    toast.classList.remove("hidden");
    setTimeout(function () {
        toast.classList.add("hidden");
    }, 3000);
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function login() {
    devPassword = document.getElementById("login-password").value;
    if (!devPassword) return;

    apiGet("/system/health")
        .then(function () {
            document.getElementById("login-modal").classList.add("hidden");
            document.getElementById("main-dashboard").classList.remove("hidden");
            loadDashboard();
        })
        .catch(function () {
            document.getElementById("login-error").classList.remove("hidden");
            devPassword = null;
        });
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

function apiGet(path) {
    return fetch("/dev" + path, {
        headers: { "X-Dev-Password": devPassword },
    }).then(function (res) {
        if (res.status === 401) throw new Error("Unauthorized");
        if (!res.ok) throw new Error("API error: " + res.status);
        return res.json();
    });
}

function apiPost(path, body) {
    return fetch("/dev" + path, {
        method: "POST",
        headers: {
            "X-Dev-Password": devPassword,
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    }).then(function (res) {
        if (res.status === 401) throw new Error("Unauthorized");
        if (!res.ok) {
            return res.json().then(function (err) {
                throw new Error(err.detail || "API error");
            });
        }
        return res.json();
    });
}

function apiDelete(path) {
    return fetch("/dev" + path, {
        method: "DELETE",
        headers: { "X-Dev-Password": devPassword },
    }).then(function (res) {
        if (!res.ok) throw new Error("API error: " + res.status);
        return res.json();
    });
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function switchTab(tab) {
    var tabs = ["features", "monitoring", "config"];
    tabs.forEach(function (t) {
        document.getElementById("panel-" + t).classList.toggle("hidden", t !== tab);
        document.getElementById("tab-" + t).classList.toggle("tab-active", t === tab);
    });

    if (tab === "features") loadFeatures();
    if (tab === "monitoring") loadMonitoring();
    if (tab === "config") loadConfig();
}

// ---------------------------------------------------------------------------
// Dashboard init
// ---------------------------------------------------------------------------

function loadDashboard() {
    loadFeatures();
    loadHeaderBadges();
}

function loadHeaderBadges() {
    apiGet("/system/health").then(function (data) {
        document.getElementById("env-badge").textContent = data.environment;
        var hb = document.getElementById("health-badge");
        if (data.status === "healthy") {
            hb.textContent = "HEALTHY";
            hb.className = "bg-green-600/20 text-green-400 px-3 py-1 rounded-full text-xs font-medium";
        } else {
            hb.textContent = "DEGRADED";
            hb.className = "bg-red-600/20 text-red-400 px-3 py-1 rounded-full text-xs font-medium";
        }
    });
}

// ---------------------------------------------------------------------------
// Feature Flags
// ---------------------------------------------------------------------------

function loadFeatures() {
    apiGet("/features")
        .then(function (features) {
            renderFeatures(features);
        })
        .catch(function (e) {
            showToast("Failed to load features: " + e.message, "error");
        });
}

function renderFeatures(features) {
    var container = document.getElementById("features-list");
    var html = "";

    var featureDescriptions = {
        multilingual: "Multi-language support (NL, FR, EN, DA)",
        b2b: "B2B customer features and pricing",
        calculator: "Swimming pool cost calculator",
        youtube: "YouTube video integration",
        crm: "CRM system integration",
    };

    Object.keys(features).forEach(function (name) {
        var f = features[name];
        var isOverride = f.source === "manual_override";
        var isEnabled = f.enabled;

        var sourceBadge = "";
        if (f.source === "manual_override") {
            sourceBadge =
                '<span class="bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded text-xs">OVERRIDE by ' +
                escapeHtml(f.override_by || "unknown") + "</span>";
        } else if (f.source === "date_based") {
            sourceBadge = '<span class="bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded text-xs">DATE ACTIVE</span>';
        } else {
            sourceBadge =
                '<span class="bg-gray-600/30 text-gray-400 px-2 py-0.5 rounded text-xs">SCHEDULED: ' +
                (f.release_date || "unknown") + "</span>";
        }

        var statusDot = isEnabled
            ? '<span class="w-3 h-3 rounded-full bg-green-500 inline-block"></span>'
            : '<span class="w-3 h-3 rounded-full bg-gray-600 inline-block"></span>';

        var actions = "";
        if (isOverride) {
            actions =
                '<button onclick="toggleFeature(\'' + name + "', " + !isEnabled +
                ')" class="text-xs px-3 py-1.5 rounded-lg border border-gray-600 hover:bg-gray-700 transition">' +
                (isEnabled ? "Disable" : "Enable") + "</button>" +
                '<button onclick="removeOverride(\'' + name +
                '\')" class="text-xs px-3 py-1.5 rounded-lg border border-yellow-600/50 text-yellow-400 hover:bg-yellow-600/10 transition">Remove Override</button>';
        } else {
            actions =
                '<button onclick="toggleFeature(\'' + name +
                '\', true)" class="text-xs px-3 py-1.5 rounded-lg border border-green-600/50 text-green-400 hover:bg-green-600/10 transition">Force Enable</button>' +
                '<button onclick="toggleFeature(\'' + name +
                '\', false)" class="text-xs px-3 py-1.5 rounded-lg border border-red-600/50 text-red-400 hover:bg-red-600/10 transition">Force Disable</button>';
        }

        html +=
            '<div class="bg-gray-800 rounded-xl border border-gray-700 p-4">' +
            '<div class="flex items-start justify-between gap-4">' +
            "<div class=\"flex-1\">" +
            '<div class="flex items-center gap-2 mb-1">' +
            statusDot +
            '<span class="font-semibold text-white">' + name + "</span>" +
            sourceBadge +
            "</div>" +
            '<p class="text-xs text-gray-400 mb-2">' + (featureDescriptions[name] || "") + "</p>" +
            (f.notes ? '<p class="text-xs text-gray-500 italic mb-2">Note: ' + escapeHtml(f.notes) + "</p>" : "") +
            '<div class="flex gap-2">' + actions + "</div>" +
            "</div>" +
            '<div class="text-right">' +
            '<span class="text-lg font-bold ' + (isEnabled ? "text-green-400" : "text-gray-600") + '">' +
            (isEnabled ? "ON" : "OFF") + "</span>" +
            "</div>" +
            "</div>" +
            "</div>";
    });

    container.innerHTML = html;
}

function toggleFeature(name, enabled) {
    var notes = prompt("Reason for " + (enabled ? "enabling" : "disabling") + " " + name + ":");
    if (notes === null) return;

    var overrideBy = prompt("Your name:");
    if (!overrideBy) return;

    apiPost("/features/" + name + "/toggle", {
        enabled: enabled,
        override_by: overrideBy,
        notes: notes,
    })
        .then(function () {
            showToast(name + " " + (enabled ? "enabled" : "disabled"), "success");
            loadFeatures();
        })
        .catch(function (e) {
            showToast("Failed: " + e.message, "error");
        });
}

function removeOverride(name) {
    if (!confirm("Remove manual override for " + name + "?\nIt will revert to date-based activation.")) return;

    apiDelete("/features/" + name + "/override")
        .then(function () {
            showToast("Override removed for " + name, "success");
            loadFeatures();
        })
        .catch(function (e) {
            showToast("Failed: " + e.message, "error");
        });
}

// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

function loadMonitoring() {
    apiGet("/system/stats")
        .then(function (stats) {
            document.getElementById("stat-convos").textContent = stats.conversations;
            document.getElementById("stat-kb").textContent = stats.knowledge_base;
            document.getElementById("stat-drafts").textContent = stats.pending_drafts;
            document.getElementById("stat-conf").textContent = Math.round(stats.avg_confidence * 100) + "%";
            document.getElementById("stat-approved").textContent = stats.approved_drafts;
            document.getElementById("stat-signals").textContent = stats.unprocessed_signals;
            document.getElementById("stat-chroma").textContent = stats.chromadb_documents;

            var nightlyEl = document.getElementById("stat-nightly");
            if (stats.nightly_learning_enabled) {
                nightlyEl.textContent = "ON";
                nightlyEl.className = "text-2xl font-bold text-green-400 mt-1";
            } else {
                nightlyEl.textContent = "OFF";
                nightlyEl.className = "text-2xl font-bold text-gray-500 mt-1";
            }
        })
        .catch(function (e) {
            showToast("Failed to load stats: " + e.message, "error");
        });

    apiGet("/system/health")
        .then(function (data) {
            renderHealthComponents(data.components || {});
        })
        .catch(function (e) {
            showToast("Failed to load health: " + e.message, "error");
        });
}

function renderHealthComponents(components) {
    var container = document.getElementById("health-components");
    var html = "";

    Object.keys(components).forEach(function (name) {
        var c = components[name];
        var isOk = c.status === "connected" || c.status === "configured";

        html +=
            '<div class="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-center justify-between">' +
            '<div class="flex items-center gap-3">' +
            '<span class="w-3 h-3 rounded-full ' + (isOk ? "bg-green-500" : "bg-red-500") + '"></span>' +
            '<div>' +
            '<p class="font-medium text-white text-sm">' + escapeHtml(name) + "</p>" +
            (c.documents !== undefined ? '<p class="text-xs text-gray-500">' + c.documents + " documents</p>" : "") +
            (c.detail ? '<p class="text-xs text-red-400">' + escapeHtml(c.detail) + "</p>" : "") +
            "</div>" +
            "</div>" +
            '<span class="text-xs font-medium ' + (isOk ? "text-green-400" : "text-red-400") + '">' +
            c.status.toUpperCase() + "</span>" +
            "</div>";
    });

    container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

function loadConfig() {
    apiGet("/system/config")
        .then(function (config) {
            renderConfig(config);
        })
        .catch(function (e) {
            showToast("Failed to load config: " + e.message, "error");
        });
}

function renderConfig(config) {
    var container = document.getElementById("config-view");
    var html = "";

    var sections = [
        { title: "AI Models", data: config.models },
        { title: "Thresholds", data: config.thresholds },
        { title: "Learning Engine", data: config.learning },
        { title: "Languages", data: config.languages },
        { title: "Feature Release Schedule", data: config.feature_schedule },
    ];

    sections.forEach(function (section) {
        html += '<div class="bg-gray-800 rounded-xl border border-gray-700 p-4">';
        html += '<h3 class="text-sm font-semibold text-purple-400 mb-3">' + section.title + "</h3>";
        html += '<div class="space-y-2">';

        Object.keys(section.data).forEach(function (key) {
            var val = section.data[key];
            var displayVal = Array.isArray(val) ? val.join(", ") : String(val);

            var valColor = "text-gray-300";
            if (val === true) { displayVal = "true"; valColor = "text-green-400"; }
            else if (val === false) { displayVal = "false"; valColor = "text-red-400"; }
            else if (typeof val === "number") { valColor = "text-blue-400"; }

            html +=
                '<div class="flex justify-between items-center py-1 border-b border-gray-700/50">' +
                '<span class="text-xs text-gray-400 font-mono">' + key + "</span>" +
                '<span class="text-xs font-mono ' + valColor + '">' + escapeHtml(displayVal) + "</span>" +
                "</div>";
        });

        html += "</div></div>";
    });

    container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
