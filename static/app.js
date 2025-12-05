const apiBase = "";

function el(q) { return document.querySelector(q) }

function escapeHtml(s) { return s && s.replace ? s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : s }

function getBadgeClass(type, value) {
    const v = String(value).toLowerCase();
    if (type === 'cost') {
        if (v.includes('low')) return 'badge-green';
        if (v.includes('medium')) return 'badge-yellow';
        if (v.includes('high')) return 'badge-red';
    }
    if (type === 'difficulty') {
        if (v.includes('easy')) return 'badge-green';
        if (v.includes('medium')) return 'badge-yellow';
        if (v.includes('hard')) return 'badge-red';
    }
    return 'badge-gray';
}

function createCard(h, index) {
    const div = document.createElement("div")
    div.className = "hobby-card fade-in"
    div.style.animationDelay = `${index * 150}ms`;

    const costBadge = getBadgeClass('cost', h.cost_level);
    const diffBadge = getBadgeClass('difficulty', h.difficulty);

    const score = typeof h.match_score !== "undefined" ? h.match_score : 0;
    const scorePct = Math.min(Math.max(score * 10, 0), 100);

    const why = (h.why_fit && h.why_fit.length)
        ? h.why_fit.map(s => `<li>${escapeHtml(s)}</li>`).join("")
        : "<li>Compatible match detected.</li>";

    const how = (h.how_to_start && h.how_to_start.length)
        ? h.how_to_start.map(s => `<li>${escapeHtml(s)}</li>`).join("")
        : "<li>Initialize startup sequence.</li>";

    div.innerHTML = `
    <div class="card-header">
        <h3 class="card-title">${escapeHtml(h.name || "Unknown")}</h3>
        <div class="badges">
            <span class="badge ${costBadge}">${escapeHtml(h.cost_level || "Unknown")}</span>
            <span class="badge ${diffBadge}">${escapeHtml(h.difficulty || "Unknown")}</span>
        </div>
    </div>

    <p class="card-desc">${escapeHtml(h.short || "")}</p>

    <div class="info-grid">
        <div class="info-box">
            <span class="info-label">WHY IT FITS</span>
            <ul class="info-list">${why}</ul>
        </div>
        <div class="info-box">
            <span class="info-label">HOW TO START</span>
            <ul class="info-list">${how}</ul>
        </div>
    </div>

    <div class="score-section">
        <div class="flex justify-between items-end mb-1">
            <span class="score-label">TIME REQUIRED: ${escapeHtml(String(h.time_per_week_hours ?? "?"))} HRS/WK</span>
            <span class="score-label">MATCH PROBABILITY: ${score}/10</span>
        </div>
        <div class="score-bar-bg">
            <div class="score-bar-fill" style="width: ${scorePct}%"></div>
        </div>
    </div>
  `
    return div
}

function setResultsHtml(html) {
    const results = el("#results")
    results.innerHTML = html
}

async function fetchSuggest(payload) {
    const r = await fetch(apiBase + "/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    return r
}

function buildPayload() {
    return {
        interest: (el("#interest") && el("#interest").value) ? el("#interest").value.trim() : "",
        environment: el("#environment").value,
        physical: el("#physical") ? el("#physical").value : "low",
        creative: el("#creative").value,
        social: el("#social").value,
        budget: el("#budget").value,
        time: el("#time").value
    }
}

function attachHandlers() {
    const findBtn = el("#findBtn")
    const allBtn = el("#allBtn")
    if (!findBtn || !allBtn) {
        console.error("UI elements missing")
        return
    }

    findBtn.addEventListener("click", async () => {
        const payload = buildPayload()
        findBtn.disabled = true
        const oldText = findBtn.innerText
        findBtn.innerText = "Finding..."
        setResultsHtml('<div class="text-center py-8 text-gray-500 animate-pulse">Analyzing your preferences...</div>')
        try {
            const r = await fetchSuggest(payload)
            if (!r.ok) {
                const txt = await r.text()
                setResultsHtml(`<div class="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">Server error ${r.status}: ${escapeHtml(txt)}</div>`)
                console.error("Server error", r.status, txt)
                return
            }
            const data = await r.json()
            if (!Array.isArray(data) || data.length === 0) {
                setResultsHtml('<div class="text-center py-8 text-gray-500">No matches found. Try adjusting your filters.</div>')
                return
            }
            setResultsHtml("")
            data.slice(0, 3).forEach((h, i) => el("#results").appendChild(createCard(h, i)))
        } catch (err) {
            console.error(err)
            setResultsHtml(`<div class="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">Network error: ${escapeHtml(String(err))}</div>`)
        } finally {
            findBtn.disabled = false
            findBtn.innerText = oldText
        }
    })

    allBtn.addEventListener("click", async () => {
        allBtn.disabled = true
        const oldText = allBtn.innerText
        allBtn.innerText = "Loading..."
        setResultsHtml('<div class="text-center py-8 text-gray-500 animate-pulse">Loading all hobbies...</div>')
        try {
            const r = await fetch(apiBase + "/hobbies")
            if (!r.ok) {
                setResultsHtml(`<div class="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">Server error ${r.status}</div>`)
                return
            }
            const data = await r.json()
            if (!Array.isArray(data) || data.length === 0) {
                setResultsHtml('<div class="text-center py-8 text-gray-500">No hobbies available.</div>')
                return
            }
            setResultsHtml("")
            data.slice(0, 10).forEach((h, i) => el("#results").appendChild(createCard(h, i)))
        } catch (err) {
            console.error(err)
            setResultsHtml(`<div class="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">Network error: ${escapeHtml(String(err))}</div>`)
        } finally {
            allBtn.disabled = false
            allBtn.innerText = oldText
        }
    })
}

function initParticles() {
    const particlesContainer = document.getElementById('particles-container');
    if (!particlesContainer) return;

    const particleCount = 80;

    for (let i = 0; i < particleCount; i++) {
        createParticle(particlesContainer);
    }

    document.addEventListener('mousemove', (e) => {
        const mouseX = (e.clientX / window.innerWidth) * 100;
        const mouseY = (e.clientY / window.innerHeight) * 100;

        const particle = document.createElement('div');
        particle.className = 'particle';

        const size = Math.random() * 4 + 2;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;

        particle.style.left = `${mouseX}%`;
        particle.style.top = `${mouseY}%`;
        particle.style.opacity = '0.6';

        particlesContainer.appendChild(particle);

        setTimeout(() => {
            particle.style.transition = 'all 2s ease-out';
            particle.style.left = `${mouseX + (Math.random() * 10 - 5)}%`;
            particle.style.top = `${mouseY + (Math.random() * 10 - 5)}%`;
            particle.style.opacity = '0';

            setTimeout(() => {
                particle.remove();
            }, 2000);
        }, 10);

        const spheres = document.querySelectorAll('.gradient-sphere');
        const moveX = (e.clientX / window.innerWidth - 0.5) * 5;
        const moveY = (e.clientY / window.innerHeight - 0.5) * 5;

        spheres.forEach(sphere => {
            sphere.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });
    });
}

function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'particle';

    const size = Math.random() * 3 + 1;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;

    const pos = resetParticle(particle);

    container.appendChild(particle);

    animateParticle(particle);
}

function resetParticle(particle) {
    const posX = Math.random() * 100;
    const posY = Math.random() * 100;

    particle.style.left = `${posX}%`;
    particle.style.top = `${posY}%`;
    particle.style.opacity = '0';

    return {
        x: posX,
        y: posY
    };
}

function animateParticle(particle) {
    const pos = resetParticle(particle);

    const duration = Math.random() * 10 + 10;
    const delay = Math.random() * 5;

    setTimeout(() => {
        particle.style.transition = `all ${duration}s linear`;
        particle.style.opacity = Math.random() * 0.3 + 0.1;

        const moveX = pos.x + (Math.random() * 20 - 10);
        const moveY = pos.y - Math.random() * 30;

        particle.style.left = `${moveX}%`;
        particle.style.top = `${moveY}%`;

        setTimeout(() => {
            animateParticle(particle);
        }, duration * 1000);
    }, delay * 1000);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        attachHandlers();
        initParticles();
    })
} else {
    attachHandlers();
    initParticles();
}
