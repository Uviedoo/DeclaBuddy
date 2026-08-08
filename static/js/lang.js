let globalFilesArray = [];
let currentLanguage = 'nl';
let signatureMode = 'draw';
let uploadedSignatureBase64 = "";

// File size limits
const MAX_FILE_SIZE_MB = 25; // 25 MB
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

function switchLanguage(lang) {
    currentLanguage = lang;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    if (event && event.target) { event.target.classList.add('active'); }
    
    document.querySelectorAll('.lang-el').forEach(el => {
        if (el.getAttribute('lang') === lang) { el.classList.remove('lang-hidden'); } 
        else { el.classList.add('lang-hidden'); }
    });

    const nlPrivacy = document.getElementById('privacy-nl');
    const enPrivacy = document.getElementById('privacy-en');
    if (nlPrivacy && enPrivacy) {
        if (lang === 'nl') {
            nlPrivacy.classList.remove('lang-hidden');
            enPrivacy.classList.add('lang-hidden');
        } else {
            nlPrivacy.classList.add('lang-hidden');
            enPrivacy.classList.remove('lang-hidden');
        }
    }
    updateVisualFileList();
}

function setCurrentSubmissionDate() {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const subDateInput = document.getElementById("submissionDateInput");
    if (subDateInput) subDateInput.value = `${yyyy}-${mm}-${dd}`;
}

const dropZone = document.getElementById("dropZone");

if (dropZone) {
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => { e.preventDefault(); dropZone.classList.add('dragover'); }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        addFilesToDataArray(e.dataTransfer.files);
    });
}

function addFilesToDataArray(files) {
    if (!files) return;
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.size > MAX_FILE_SIZE_BYTES) {
            const msg = currentLanguage === 'nl' 
                ? `Bestand "${file.name}" is te groot. Maximale bestandsgrootte is ${MAX_FILE_SIZE_MB} MB.`
                : `File "${file.name}" is too large. Maximum file size is ${MAX_FILE_SIZE_MB} MB.`;
            alert(msg);
            continue; // Skip oversized files
        }
        globalFilesArray.push(file);
    }
    updateVisualFileList();
}

function truncateFilename(filename, maxLength = 28) {
    if (filename.length <= maxLength) return filename;
    
    const extIndex = filename.lastIndexOf('.');
    if (extIndex !== -1 && filename.length - extIndex <= 6) {
        const ext = filename.substring(extIndex);
        const nameWithoutExt = filename.substring(0, extIndex);
        const availableChars = maxLength - ext.length - 3; // 3 for "..."
        if (availableChars > 3) {
            return nameWithoutExt.substring(0, availableChars) + "..." + ext;
        }
    }
    return filename.substring(0, maxLength - 3) + "...";
}

function updateVisualFileList() {
    const listDisplay = document.getElementById("selectedFilesList");
    if (!listDisplay) return;
    listDisplay.innerHTML = "";
    globalFilesArray.forEach((file, index) => {
        const li = document.createElement("li");
        li.className = "file-item";
        
        const truncatedName = truncateFilename(file.name, 28);
        
        li.innerHTML = `
            <span title="${file.name}">📎 ${truncatedName} (${(file.size/1024).toFixed(1)} KB)</span>
            <button type="button" class="remove-file-btn" onclick="removeFileFromBuffer(${index})">${currentLanguage === 'nl' ? 'Verwijder' : 'Remove'}</button>
        `;
        listDisplay.appendChild(li);
    });
}

function removeFileFromBuffer(index) {
    globalFilesArray.splice(index, 1);
    updateVisualFileList();
}

function switchSignatureMode(mode) {
    signatureMode = mode;
    const tabDraw = document.getElementById("tabDraw");
    const tabUpload = document.getElementById("tabUpload");
    const sigContentDraw = document.getElementById("sigContentDraw");
    const sigContentUpload = document.getElementById("sigContentUpload");

    if (tabDraw) tabDraw.classList.toggle("active", mode === 'draw');
    if (tabUpload) tabUpload.classList.toggle("active", mode === 'upload');
    if (sigContentDraw) sigContentDraw.classList.toggle("active", mode === 'draw');
    if (sigContentUpload) sigContentUpload.classList.toggle("active", mode === 'upload');
}

function processSignatureFile(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) { uploadedSignatureBase64 = e.target.result; };
        reader.readAsDataURL(input.files[0]);
    }
}

const globalResetBtn = document.getElementById("globalResetBtn");
if (globalResetBtn) {
    globalResetBtn.addEventListener("click", function() {
        if (confirm(currentLanguage === 'nl' ? "Weet je zeker dat je alle ingevoerde gegevens wilt wissen?" : "Are you sure you want to clear all data?")) {
            document.getElementById("claimForm").reset();
            globalFilesArray = [];
            uploadedSignatureBase64 = "";
            updateVisualFileList();
            if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
            const totaalDisplay = document.getElementById("Totaal_Display");
            if (totaalDisplay) totaalDisplay.value = "0,00";
        }
    });
}

// ==========================================
// MODAL CONTROLS (PRIVACY & ABOUT)
// ==========================================
const privacyModal = document.getElementById("privacyModal");
function openPrivacyModal() { if (privacyModal) privacyModal.style.display = "flex"; }
function closePrivacyModal() { if (privacyModal) privacyModal.style.display = "none"; }

const aboutModal = document.getElementById("aboutModal");
function openAboutModal() { if (aboutModal) aboutModal.style.display = "flex"; }
function closeAboutModal() { if (aboutModal) aboutModal.style.display = "none"; }

window.onclick = function(event) {
    if (event.target === privacyModal) { closePrivacyModal(); }
    if (event.target === aboutModal) { closeAboutModal(); }
};

document.addEventListener("input", function(e) {
    if (e.target.classList.contains("expense-amount")) {
        let total = 0;
        document.querySelectorAll(".expense-amount").forEach(input => {
            let val = parseFloat(input.value);
            if (!isNaN(val)) { total += val; }
        });
        const totaalDisplay = document.getElementById("Totaal_Display");
        if (totaalDisplay) totaalDisplay.value = total.toFixed(2).replace(".", ",");
    }
});

const canvas = document.getElementById("sigCanvas");
let ctx = null;
let drawing = false;

if (canvas) {
    ctx = canvas.getContext("2d");
    function resizeCanvas() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.strokeStyle = "#000000";
    }
    window.addEventListener("resize", resizeCanvas);
    document.addEventListener("DOMContentLoaded", resizeCanvas);

    canvas.addEventListener("mousedown", (e) => { drawing = true; draw(e); });
    canvas.addEventListener("mouseup", () => { drawing = false; ctx.beginPath(); });
    canvas.addEventListener("mousemove", draw);
    canvas.addEventListener("touchstart", (e) => { drawing = true; draw(e); e.preventDefault(); });
    canvas.addEventListener("touchend", () => { drawing = false; ctx.beginPath(); });
    canvas.addEventListener("touchmove", (e) => { draw(e); e.preventDefault(); });

    function draw(e) {
        if (!drawing) return;
        let clientX = e.touches ? e.touches[0].clientX : e.clientX;
        let clientY = e.touches ? e.touches[0].clientY : e.clientY;
        const rect = canvas.getBoundingClientRect();
        const x = clientX - rect.left;
        const y = clientY - rect.top;
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x, y);
    }

    const clearBtn = document.getElementById("clearBtn");
    if (clearBtn) {
        clearBtn.addEventListener("click", () => { ctx.clearRect(0, 0, canvas.width, canvas.height); });
    }
}

const claimForm = document.getElementById("claimForm");
if (claimForm) {
    claimForm.addEventListener("submit", function(e) {
        if (canvas) {
            const blank = document.createElement('canvas');
            blank.width = canvas.width;
            blank.height = canvas.height;
            
            if (signatureMode === 'draw' && canvas.toDataURL() === blank.toDataURL()) {
                alert(currentLanguage === 'nl' ? "Zet alsjeblieft je handtekening voor het indienen van het formulier." : "Please provide a signature before submitting.");
                e.preventDefault();
                return;
            }
        }
        
        if (globalFilesArray.length === 0) {
            alert(currentLanguage === 'nl' ? "Voeg minimaal één bonnetje of bewijslast toe." : "Please upload at least one receipt as proof.");
            e.preventDefault();
            return;
        }

        const finalSignaturePayload = (signatureMode === 'draw' && canvas) ? canvas.toDataURL() : uploadedSignatureBase64;
        const sigInput = document.getElementById("Handtekening_data");
        if (sigInput) sigInput.value = finalSignaturePayload;

        const dataTransfer = new DataTransfer();
        globalFilesArray.forEach(file => {
            dataTransfer.items.add(file);
        });
        
        const hiddenFileInput = document.getElementById("hiddenFileInput");
        if (hiddenFileInput) hiddenFileInput.files = dataTransfer.files;

        // Display the loading lightbox modal
        const loadingModal = document.getElementById("loadingModal");
        if (loadingModal) {
            loadingModal.classList.add("active");

            // Hide the modal when the browser regains focus (after download completes/prompts)
            setTimeout(() => {
                window.addEventListener('focus', function clearModal() {
                    loadingModal.classList.remove("active");
                    window.removeEventListener('focus', clearModal);
                }, { once: true });
            }, 1500); // 1.5s delay prevents instant triggering
        }
    });
}

// Official SEPA Country Registry Length Map
const countryIbanLengths = {
    "NL": 18, "BE": 16, "DE": 22, "FR": 27, "GB": 22, 
    "ES": 24, "IT": 27, "CH": 21, "AT": 20, "PT": 25,
    "IE": 22, "LU": 20, "PL": 28, "DK": 18, "FI": 18, 
    "SE": 24, "NO": 15, "GR": 27, "TR": 26, "CZ": 24,
    "HU": 28, "RO": 24, "SK": 24, "BG": 22, "HR": 21
};

function isValidIBAN(iban) {
    if (!iban) return false;
    const country = iban.substring(0, 2);
    const expectedLength = countryIbanLengths[country];
    if (!expectedLength || iban.length !== expectedLength) return false;

    const rearranged = iban.substring(4) + iban.substring(0, 4);
    let numericString = "";
    for (let i = 0; i < rearranged.length; i++) {
        const charCode = rearranged.charCodeAt(i);
        if (charCode >= 65 && charCode <= 90) {
            numericString += (charCode - 55).toString();
        } else {
            numericString += rearranged[i];
        }
    }

    let remainder = numericString;
    while (remainder.length > 7) {
        const block = remainder.substring(0, 7);
        remainder = (parseInt(block, 10) % 97).toString() + remainder.substring(7);
    }
    
    return (parseInt(remainder, 10) % 97) === 1;
}

const ibanInput = document.getElementById('ibanInput');
if (ibanInput) {
    ibanInput.addEventListener('input', function (e) {
        let inputEl = e.target;
        let rawValue = inputEl.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
        
        let countryCode = rawValue.substring(0, 2);
        let allowedLength = countryIbanLengths[countryCode] || 34;
        
        if (rawValue.length > allowedLength) {
            rawValue = rawValue.substring(0, allowedLength);
        }
        
        inputEl.maxLength = allowedLength + Math.floor((allowedLength - 1) / 4);
        inputEl.value = rawValue.match(/.{1,4}/g)?.join(' ') || rawValue;

        if (rawValue.length === 0) {
            inputEl.style.borderColor = "";
            inputEl.style.backgroundColor = "";
        } else if (rawValue.length === allowedLength) {
            if (isValidIBAN(rawValue)) {
                inputEl.style.borderColor = "#28a745";
                inputEl.style.backgroundColor = "#f4fff5";
                inputEl.setCustomValidity("");
            } else {
                inputEl.style.borderColor = "#dc3545";
                inputEl.style.backgroundColor = "#fff5f5";
                inputEl.setCustomValidity(currentLanguage === 'nl' ? "Ongeldig IBAN-nummer." : "Invalid IBAN format.");
            }
        } else {
            inputEl.style.borderColor = "#ffc107";
            inputEl.style.backgroundColor = "";
            inputEl.setCustomValidity(currentLanguage === 'nl' ? "IBAN is nog niet compleet." : "IBAN is incomplete.");
        }
    });
}

// LOCAL HOSTED ADDRESS LOOKUP INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
    const postcodeEl = document.getElementById('postcode');
    const huisnrEl = document.getElementById('huisnummer');
    const straatEl = document.getElementById('straatnaam');
    const woonplaatsEl = document.getElementById('woonplaats');
    const statusEl = document.getElementById('address-status');

    if (postcodeEl && huisnrEl) {
        postcodeEl.addEventListener('change', lookupAddress);
        huisnrEl.addEventListener('change', lookupAddress);
    }

    async function lookupAddress() {
        let postcode = postcodeEl.value.replace(/\s+/g, '').toUpperCase();
        let huisnummer = huisnrEl.value.trim();

        const postcodeRegex = /^[1-9][0-9]{3}[A-Z]{2}$/;

        if (!postcodeRegex.test(postcode) || !huisnummer) {
            return;
        }

        showAddressStatus('Adres zoeken...', 'Looking up address...', '#666');

        try {
            const url = `/api/address-lookup?postcode=${encodeURIComponent(postcode)}&huisnummer=${encodeURIComponent(huisnummer)}`;

            const response = await fetch(url);
            const data = await response.json();

            if (response.ok && data.success) {
                if (straatEl) straatEl.value = data.full_address || `${data.straat} ${huisnummer}`;
                if (woonplaatsEl) woonplaatsEl.value = data.woonplaats;

                showAddressStatus(
                    '✓ Adres automatisch ingevuld', 
                    '✓ Address automatically found', 
                    '#2e7d32'
                );
            } else {
                showAddressStatus(
                    'Adres niet gevonden. Vul handmatig in.', 
                    'Address not found. Please fill manually.', 
                    '#d32f2f'
                );
            }
        } catch (error) {
            console.error('Local Address Lookup Error:', error);
            showAddressStatus(
                'Ophalen mislukt. Vul handmatig in.', 
                'Lookup failed. Please fill manually.', 
                '#d32f2f'
            );
        }
    }

    function showAddressStatus(nlMsg, enMsg, color) {
        if (!statusEl) return;
        statusEl.style.display = 'block';
        statusEl.style.color = color;
        statusEl.innerHTML = `
            <span class="lang-el ${currentLanguage === 'nl' ? '' : 'lang-hidden'}" lang="nl">${nlMsg}</span>
            <span class="lang-el ${currentLanguage === 'en' ? '' : 'lang-hidden'}" lang="en">${enMsg}</span>
        `;
    }
});