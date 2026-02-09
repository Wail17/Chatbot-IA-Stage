/**
 * Zwembad.eu AI Chatbot - Admin Dashboard
 *
 * Vanilla JS dashboard for Human-in-the-Loop learning management.
 * Communicates with FastAPI backend via fetch API.
 */

const API_BASE = window.location.origin + "/api";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let currentTab = "drafts";
let kbPage = 0;
const KB_PAGE_SIZE = 50;
let searchTimeout = null;
let conversationChart = null;
let knowledgeChart = null;

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function showToast(message, type) {
    const toast = document.getElementById("toast");
    const inner = toast.querySelector("div");
    inner.textContent = message;
    inner.className =
        "rounded-lg px-4 py-3 shadow-lg text-white text-sm font-medium " +
        (type === "error"
            ? "bg-red-600"
            : type === "warning"
              ? "bg-yellow-600"
              : "bg-green-600");
    toast.classList.remove("hidden");
    setTimeout(function () {
        toast.classList.add("hidden");
    }, 3000);
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function switchTab(tab) {
    currentTab = tab;
    var tabs = ["drafts", "knowledge", "analytics"];
    tabs.forEach(function (t) {
        document.getElementById("panel-" + t).classList.toggle("hidden", t !== tab);
        document.getElementById("tab-" + t).classList.toggle("tab-active", t === tab);
    });

    if (tab === "drafts") loadDrafts();
    if (tab === "knowledge") loadKnowledge();
    if (tab === "analytics") loadAnalytics();
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet(path) {
    var res = await fetch(API_BASE + path);
    if (!res.ok) throw new Error("API error: " + res.status);
    return res.json();
}

async function apiPost(path, body) {
    var res = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        var err = await res.json().catch(function () {
            return { detail: "Unknown error" };
        });
        throw new Error(err.detail || "API error");
    }
    return res.json();
}

async function apiPut(path, body) {
    var res = await fetch(API_BASE + path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        var err = await res.json().catch(function () {
            return { detail: "Unknown error" };
        });
        throw new Error(err.detail || "API error");
    }
    return res.json();
}

async function apiDelete(path) {
    var res = await fetch(API_BASE + path, { method: "DELETE" });
    if (!res.ok) throw new Error("API error: " + res.status);
    return res.json();
}

// ---------------------------------------------------------------------------
// Drafts
// ---------------------------------------------------------------------------

async function loadDrafts() {
    var status = document.getElementById("draft-filter").value;
    try {
        var drafts = await apiGet("/admin/drafts?status=" + status + "&limit=100");
        renderDrafts(drafts, status);
    } catch (e) {
        showToast("Failed to load drafts: " + e.message, "error");
    }
}

function renderDrafts(drafts, status) {
    var container = document.getElementById("drafts-list");

    if (drafts.length === 0) {
        container.innerHTML =
            '<div class="text-center py-12 text-gray-400">' +
            '<p class="text-lg">No ' + status + ' drafts</p>' +
            '<p class="text-sm mt-1">New drafts appear after learning cycles detect patterns.</p>' +
            "</div>";
        return;
    }

    var html = "";
    drafts.forEach(function (d) {
        var sourceLabel =
            d.source === "user_correction"
                ? '<span class="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs">User Correction</span>'
                : d.source === "pattern_detection"
                  ? '<span class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">Pattern Detection (' + d.pattern_count + ")</span>"
                  : '<span class="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs">' + d.source + "</span>";

        var confidenceColor =
            d.confidence >= 0.8
                ? "text-green-600"
                : d.confidence >= 0.6
                  ? "text-yellow-600"
                  : "text-red-600";

        var actions = "";
        if (status === "pending") {
            actions =
                '<div class="flex gap-2 mt-3">' +
                '<button onclick="reviewDraft(' + d.id + ', \'approve\')" class="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 transition">Approve</button>' +
                '<button onclick="reviewDraft(' + d.id + ', \'reject\')" class="bg-red-500 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-red-600 transition">Reject</button>' +
                '<button onclick="openEditDraft(' + d.id + "," + JSON.stringify(d.question).replace(/"/g, "&quot;") + "," + JSON.stringify(d.answer).replace(/"/g, "&quot;") + ",'" + d.category + "')" + '" class="border text-gray-600 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-50 transition">Edit</button>' +
                "</div>";
        }

        html +=
            '<div class="bg-white rounded-xl shadow-sm p-4 border-l-4 ' +
            (status === "approved" ? "border-green-500" : status === "rejected" ? "border-red-400" : "border-blue-500") +
            '">' +
            '<div class="flex items-start justify-between gap-4">' +
            '<div class="flex-1">' +
            '<div class="flex items-center gap-2 mb-2">' +
            sourceLabel +
            '<span class="text-xs text-gray-400">' + d.category + "</span>" +
            '<span class="text-xs ' + confidenceColor + ' font-medium">' + Math.round(d.confidence * 100) + "% confidence</span>" +
            "</div>" +
            '<p class="font-medium text-gray-900 mb-1">' + escapeHtml(d.question) + "</p>" +
            '<p class="text-sm text-gray-600">' + escapeHtml(d.answer) + "</p>" +
            actions +
            "</div>" +
            '<span class="text-xs text-gray-400 whitespace-nowrap">#' + d.id + "</span>" +
            "</div>" +
            "</div>";
    });

    container.innerHTML = html;
}

async function reviewDraft(draftId, action) {
    try {
        await apiPost("/admin/drafts/" + draftId + "/review", { action: action });
        showToast(
            "Draft #" + draftId + " " + (action === "approve" ? "approved and added to knowledge base" : "rejected"),
            action === "approve" ? "success" : "warning"
        );
        loadDrafts();
        loadBadges();
    } catch (e) {
        showToast("Failed: " + e.message, "error");
    }
}

function openEditDraft(id, question, answer, category) {
    document.getElementById("edit-id").value = id;
    document.getElementById("edit-type").value = "draft";
    document.getElementById("edit-category").value = category;
    document.getElementById("edit-question").value = question;
    document.getElementById("edit-answer").value = answer;
    document.getElementById("edit-language-row").classList.add("hidden");
    document.getElementById("modal-title").textContent = "Edit Draft #" + id;
    document.getElementById("modal-edit").classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Knowledge Base
// ---------------------------------------------------------------------------

async function loadKnowledge() {
    var search = document.getElementById("kb-search").value;
    var params = "?limit=" + KB_PAGE_SIZE + "&offset=" + kbPage * KB_PAGE_SIZE;
    if (search) params += "&search=" + encodeURIComponent(search);

    try {
        var entries = await apiGet("/admin/knowledge" + params);
        renderKnowledge(entries);
    } catch (e) {
        showToast("Failed to load knowledge base: " + e.message, "error");
    }
}

function renderKnowledge(entries) {
    var tbody = document.getElementById("kb-table-body");
    var countEl = document.getElementById("kb-count");

    if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-12 text-center text-gray-400">No entries found</td></tr>';
        countEl.textContent = "0 entries";
        return;
    }

    var html = "";
    entries.forEach(function (e) {
        var sourceBg =
            e.source === "client_approved"
                ? "bg-green-100 text-green-700"
                : e.source === "manual"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-700";

        html +=
            "<tr class=\"border-b hover:bg-gray-50 transition\">" +
            '<td class="px-4 py-3 text-gray-400">' + e.id + "</td>" +
            '<td class="px-4 py-3"><span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">' + escapeHtml(e.category) + "</span></td>" +
            '<td class="px-4 py-3">' +
            '<p class="font-medium text-gray-900 text-sm">' + escapeHtml(truncate(e.question, 80)) + "</p>" +
            '<p class="text-xs text-gray-500 mt-0.5">' + escapeHtml(truncate(e.answer, 100)) + "</p>" +
            "</td>" +
            '<td class="px-4 py-3"><span class="' + sourceBg + ' px-2 py-0.5 rounded text-xs">' + e.source + "</span></td>" +
            '<td class="px-4 py-3">' +
            '<div class="flex gap-1">' +
            '<button onclick="openEditKB(' + e.id + "," + JSON.stringify(e.question).replace(/"/g, "&quot;") + "," + JSON.stringify(e.answer).replace(/"/g, "&quot;") + ",'" + escapeHtml(e.category) + "')" + '" class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded hover:bg-blue-50">Edit</button>' +
            '<button onclick="deleteKB(' + e.id + ')" class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50">Delete</button>' +
            "</div>" +
            "</td>" +
            "</tr>";
    });

    tbody.innerHTML = html;
    countEl.textContent = entries.length + " entries (page " + (kbPage + 1) + ")";

    document.getElementById("kb-prev").disabled = kbPage === 0;
    document.getElementById("kb-next").disabled = entries.length < KB_PAGE_SIZE;
}

function kbNextPage() {
    kbPage++;
    loadKnowledge();
}

function kbPrevPage() {
    if (kbPage > 0) kbPage--;
    loadKnowledge();
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    kbPage = 0;
    searchTimeout = setTimeout(loadKnowledge, 300);
}

function openEditKB(id, question, answer, category) {
    document.getElementById("edit-id").value = id;
    document.getElementById("edit-type").value = "knowledge";
    document.getElementById("edit-category").value = category;
    document.getElementById("edit-question").value = question;
    document.getElementById("edit-answer").value = answer;
    document.getElementById("edit-language-row").classList.add("hidden");
    document.getElementById("modal-title").textContent = "Edit Q&A #" + id;
    document.getElementById("modal-edit").classList.remove("hidden");
}

async function deleteKB(id) {
    if (!confirm("Delete Q&A #" + id + "? This also removes it from ChromaDB.")) return;
    try {
        await apiDelete("/admin/knowledge/" + id);
        showToast("Q&A #" + id + " deleted", "success");
        loadKnowledge();
        loadBadges();
    } catch (e) {
        showToast("Delete failed: " + e.message, "error");
    }
}

// ---------------------------------------------------------------------------
// Modals
// ---------------------------------------------------------------------------

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

async function saveEdit() {
    var id = document.getElementById("edit-id").value;
    var type = document.getElementById("edit-type").value;
    var question = document.getElementById("edit-question").value.trim();
    var answer = document.getElementById("edit-answer").value.trim();

    if (!question || !answer) {
        showToast("Question and answer are required", "warning");
        return;
    }

    try {
        if (type === "draft") {
            await apiPut("/admin/drafts/" + id, {
                edited_question: question,
                edited_answer: answer,
            });
            showToast("Draft #" + id + " updated", "success");
            loadDrafts();
        } else {
            await apiPut("/admin/knowledge/" + id, {
                question: question,
                answer: answer,
            });
            showToast("Q&A #" + id + " updated and re-vectorized", "success");
            loadKnowledge();
        }
        closeModal("modal-edit");
    } catch (e) {
        showToast("Save failed: " + e.message, "error");
    }
}

function showAddModal() {
    document.getElementById("add-category").value = "";
    document.getElementById("add-question").value = "";
    document.getElementById("add-answer").value = "";
    document.getElementById("add-language").value = "nl";
    document.getElementById("modal-add").classList.remove("hidden");
}

async function addNewQA() {
    var category = document.getElementById("add-category").value.trim();
    var question = document.getElementById("add-question").value.trim();
    var answer = document.getElementById("add-answer").value.trim();
    var language = document.getElementById("add-language").value;

    if (!category || !question || !answer) {
        showToast("All fields are required", "warning");
        return;
    }

    try {
        await apiPost("/admin/knowledge", {
            question: question,
            answer: answer,
            category: category,
            language: language,
        });
        showToast("New Q&A added and vectorized", "success");
        closeModal("modal-add");
        loadKnowledge();
        loadBadges();
    } catch (e) {
        showToast("Failed to add Q&A: " + e.message, "error");
    }
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

async function loadAnalytics() {
    try {
        var stats = await apiGet("/learning/stats");
        document.getElementById("stat-total-qa").textContent = stats.total_knowledge_entries;
        document.getElementById("stat-learned").textContent = stats.learned_entries || 0;
        document.getElementById("stat-signals").textContent = stats.unprocessed_signals;

        var weeks = await apiGet("/admin/analytics/weekly?weeks=12");

        if (weeks.length > 0) {
            var last = weeks[0];
            document.getElementById("stat-confidence").textContent =
                Math.round(last.avg_confidence * 100) + "%";

            renderCharts(weeks.reverse());
            renderUnanswered(last.top_unanswered || []);
        }
    } catch (e) {
        showToast("Failed to load analytics: " + e.message, "error");
    }
}

function renderCharts(weeks) {
    var labels = weeks.map(function (w) {
        return "W" + w.week_number;
    });

    // Conversations & Success Rate Chart
    var ctxConv = document.getElementById("chart-conversations").getContext("2d");
    if (conversationChart) conversationChart.destroy();
    conversationChart = new Chart(ctxConv, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Conversations",
                    data: weeks.map(function (w) { return w.total_conversations; }),
                    backgroundColor: "rgba(59, 130, 246, 0.5)",
                    borderColor: "rgb(59, 130, 246)",
                    borderWidth: 1,
                    yAxisID: "y",
                },
                {
                    label: "Success Rate %",
                    data: weeks.map(function (w) { return Math.round(w.success_rate * 100); }),
                    type: "line",
                    borderColor: "rgb(34, 197, 94)",
                    backgroundColor: "rgba(34, 197, 94, 0.1)",
                    fill: true,
                    tension: 0.3,
                    yAxisID: "y1",
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: { position: "left", beginAtZero: true, title: { display: true, text: "Conversations" } },
                y1: { position: "right", min: 0, max: 100, title: { display: true, text: "Success %" }, grid: { drawOnChartArea: false } },
            },
        },
    });

    // Knowledge Growth Chart
    var ctxKb = document.getElementById("chart-knowledge").getContext("2d");
    if (knowledgeChart) knowledgeChart.destroy();

    var cumulative = 0;
    var kbGrowth = weeks.map(function (w) {
        cumulative += w.new_qa_learned;
        return cumulative;
    });

    knowledgeChart = new Chart(ctxKb, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "New Q&A Learned",
                    data: weeks.map(function (w) { return w.new_qa_learned; }),
                    backgroundColor: "rgba(168, 85, 247, 0.5)",
                    borderColor: "rgb(168, 85, 247)",
                    type: "bar",
                    yAxisID: "y",
                },
                {
                    label: "Cumulative Growth",
                    data: kbGrowth,
                    borderColor: "rgb(249, 115, 22)",
                    backgroundColor: "rgba(249, 115, 22, 0.1)",
                    fill: true,
                    tension: 0.3,
                    yAxisID: "y1",
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: { position: "left", beginAtZero: true, title: { display: true, text: "New Q&A" } },
                y1: { position: "right", beginAtZero: true, title: { display: true, text: "Total Learned" }, grid: { drawOnChartArea: false } },
            },
        },
    });
}

function renderUnanswered(questions) {
    var el = document.getElementById("unanswered-list");
    if (questions.length === 0) {
        el.innerHTML = '<li class="text-gray-400 italic">No unanswered questions this week</li>';
        return;
    }
    el.innerHTML = questions
        .map(function (q, i) {
            return '<li class="flex items-start gap-2"><span class="text-gray-400 font-mono text-xs mt-0.5">' +
                (i + 1) + '.</span><span>' + escapeHtml(q) + '</span></li>';
        })
        .join("");
}

// ---------------------------------------------------------------------------
// Learning Trigger
// ---------------------------------------------------------------------------

async function triggerLearning() {
    try {
        showToast("Running learning cycle...", "success");
        var result = await apiPost("/learning/trigger", {});
        showToast(result.message, "success");
        loadDrafts();
        loadBadges();
    } catch (e) {
        showToast("Learning cycle failed: " + e.message, "error");
    }
}

// ---------------------------------------------------------------------------
// Badge counts
// ---------------------------------------------------------------------------

async function loadBadges() {
    try {
        var stats = await apiGet("/learning/stats");
        document.getElementById("badge-pending").textContent = stats.pending_drafts;
        document.getElementById("badge-knowledge").textContent = stats.total_knowledge_entries;
    } catch (e) {
        // Silently fail badge loading
    }
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

function truncate(text, maxLen) {
    if (!text) return "";
    return text.length > maxLen ? text.substring(0, maxLen) + "..." : text;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", function () {
    loadBadges();
    loadDrafts();
});
