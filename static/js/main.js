const root = document.documentElement;
const siteNav = document.getElementById("siteNav");
const menuToggle = document.getElementById("menuToggle");
const accountToggle = document.getElementById("accountToggle");
const accountMenu = document.getElementById("accountMenu");
const setLightThemeButton = document.getElementById("setLightTheme");
const setDarkThemeButton = document.getElementById("setDarkTheme");
const themeStatus = document.getElementById("themeStatus");

const savedTheme = localStorage.getItem("eduripple-theme");
if (savedTheme) {
    root.setAttribute("data-theme", savedTheme);
}

function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem("eduripple-theme", theme);
    setThemeStatusLabel();
}

function setThemeStatusLabel() {
    const isDark = root.getAttribute("data-theme") === "dark";
    if (themeStatus) {
        themeStatus.textContent = isDark
            ? "Current mode: Dark."
            : "Current mode: Light.";
    }
}

setThemeStatusLabel();

if (setLightThemeButton) {
    setLightThemeButton.addEventListener("click", () => {
        applyTheme("light");
    });
}

if (setDarkThemeButton) {
    setDarkThemeButton.addEventListener("click", () => {
        applyTheme("dark");
    });
}

// Mobile navigation toggle
if (menuToggle && siteNav) {
    const closeNav = () => {
        siteNav.classList.remove("open");
        menuToggle.classList.remove("active");
        menuToggle.setAttribute("aria-expanded", "false");
    };

    const openNav = () => {
        siteNav.classList.add("open");
        menuToggle.classList.add("active");
        menuToggle.setAttribute("aria-expanded", "true");
    };

    menuToggle.addEventListener("click", () => {
        if (siteNav.classList.contains("open")) {
            closeNav();
        } else {
            openNav();
        }
    });

    // Close nav when clicking a link (for mobile)
    siteNav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            if (window.innerWidth <= 760) {
                closeNav();
            }
        });
    });

    // Close nav on escape key
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && siteNav.classList.contains("open")) {
            closeNav();
        }
    });

    // Close nav when clicking outside
    document.addEventListener("click", (event) => {
        if (window.innerWidth <= 760 && 
            siteNav.classList.contains("open") && 
            !siteNav.contains(event.target) && 
            !menuToggle.contains(event.target)) {
            closeNav();
        }
    });
}

if (siteNav) {
    const links = siteNav.querySelectorAll("a");
    links.forEach((link) => {
        const linkPath = new URL(link.href).pathname;
        if (linkPath === window.location.pathname) {
            link.classList.add("active");
        }
    });
}

if (accountToggle && accountMenu) {
    const closeAccountMenu = () => {
        accountMenu.hidden = true;
        accountToggle.setAttribute("aria-expanded", "false");
    };

    const openAccountMenu = () => {
        accountMenu.hidden = false;
        accountToggle.setAttribute("aria-expanded", "true");
    };

    accountToggle.addEventListener("click", () => {
        if (accountMenu.hidden) {
            openAccountMenu();
            return;
        }
        closeAccountMenu();
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!target) return;
        if (!accountMenu.contains(target) && !accountToggle.contains(target)) {
            closeAccountMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAccountMenu();
        }
    });
}

const renderResourcesList = (resources = [], element) => {
    if (!element) return;
    element.innerHTML = "";

    if (!resources.length) {
        const item = document.createElement("li");
        item.textContent = "No generated files yet.";
        element.appendChild(item);
        return;
    }

    resources.forEach((resource) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = resource.url;
        link.textContent = resource.name;
        link.target = "_blank";
        link.rel = "noopener";
        item.appendChild(link);
        element.appendChild(item);
    });
};

const fetchResources = async (targetElementId) => {
    const targetElement = document.getElementById(targetElementId);
    if (!targetElement) return;
    try {
        const response = await fetch("/api/resources");
        const data = await response.json();
        renderResourcesList(data.resources || [], targetElement);
    } catch {
        renderResourcesList([], targetElement);
    }
};

fetchResources("libraryResourcesList");

const refreshLibrary = document.getElementById("refreshLibrary");
if (refreshLibrary) {
    refreshLibrary.addEventListener("click", () => fetchResources("libraryResourcesList"));
}

const regenerateCbcButton = document.getElementById("regenerateCbc");
if (regenerateCbcButton) {
    const regenerateStatus = document.getElementById("regenerateCbcStatus");

    regenerateCbcButton.addEventListener("click", async () => {
        regenerateCbcButton.disabled = true;
        if (regenerateStatus) {
            regenerateStatus.textContent = "Regenerating CBC parsed JSON...";
        }

        try {
            const response = await fetch("/api/regenerate-cbc", { method: "POST" });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.message || "Could not regenerate CBC JSON.");
            }

            if (regenerateStatus) {
                regenerateStatus.textContent = data.message || "CBC parsed JSON regenerated successfully.";
            }
        } catch (error) {
            if (regenerateStatus) {
                regenerateStatus.textContent = error.message || "Failed to regenerate CBC parsed JSON.";
            }
        } finally {
            regenerateCbcButton.disabled = false;
        }
    });
}

const chatForm = document.getElementById("chatForm");
if (chatForm) {
    const promptInput = document.getElementById("promptInput");
    const chatResponse = document.getElementById("chatResponse");
    const downloadLinks = document.getElementById("downloadLinks");
    const pdfDownload = document.getElementById("pdfDownload");
    const wordDownload = document.getElementById("wordDownload");
    const resourcesList = document.getElementById("resourcesList");
    fetchResources("resourcesList");

    // Only add this generic CBC handler if the ai_chat.html page hasn't added its own handler.
    // The ai_chat.html page sets window.__aiChatFormHandled = true before this script loads.
    if (!window.__aiChatFormHandled) {
        chatForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const prompt = promptInput.value.trim();
            if (!prompt) return;

            const userBubble = document.createElement("p");
            userBubble.className = "user-msg";
            userBubble.textContent = prompt;
            chatResponse.appendChild(userBubble);

            const loadingBubble = document.createElement("p");
            loadingBubble.className = "assistant-msg";
            loadingBubble.textContent = "Generating response...";
            chatResponse.appendChild(loadingBubble);
            chatResponse.scrollTop = chatResponse.scrollHeight;

            try {
                const response = await fetch("/api/cbc", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ prompt }),
                });
                const data = await response.json();
                loadingBubble.textContent = data.response || "No response received.";

                if (data.downloads && downloadLinks && pdfDownload && wordDownload) {
                    pdfDownload.href = data.downloads.pdf || "#";
                    wordDownload.href = data.downloads.word || "#";
                    downloadLinks.hidden = false;
                }

                renderResourcesList(data.resources || [], resourcesList);
                fetchResources("libraryResourcesList");
            } catch (error) {
                loadingBubble.textContent = "Could not connect to the assistant API.";
            }

            promptInput.value = "";
            chatResponse.scrollTop = chatResponse.scrollHeight;
        });
    }
}

const initHomeTabs = () => {
    const buttons = document.querySelectorAll(".tab-btn");
    const panels = document.querySelectorAll(".tab-panel");
    if (!buttons.length || !panels.length) return;

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const targetId = button.dataset.target;
            if (!targetId) return;

            buttons.forEach((btn) => {
                btn.classList.remove("active");
                btn.setAttribute("aria-selected", "false");
            });

            panels.forEach((panel) => {
                panel.classList.remove("active");
                panel.hidden = true;
            });

            const targetPanel = document.getElementById(targetId);
            if (targetPanel) {
                targetPanel.hidden = false;
                targetPanel.classList.add("active");
            }

            button.classList.add("active");
            button.setAttribute("aria-selected", "true");
        });
    });
};

const animateHomeStats = () => {
    const statValues = document.querySelectorAll("#heroStats [data-count]");
    if (!statValues.length) return;

    const runCounter = (element) => {
        const target = Number(element.dataset.count || "0");
        const suffix = element.textContent.includes("%") ? "%" : "+";
        let current = 0;
        const duration = 1200;
        const stepTime = 20;
        const increment = Math.max(1, Math.ceil(target / (duration / stepTime)));

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            element.textContent = `${current}${suffix}`;
        }, stepTime);
    };

    const observer = new IntersectionObserver(
        (entries, obs) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    runCounter(entry.target);
                    obs.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.45 }
    );

    statValues.forEach((stat) => observer.observe(stat));
};

const initScrollReveal = () => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    const targets = document.querySelectorAll(
        ".section .card, .section .step, .section h1, .section h2, .section > .container > p, .section .cta-row"
    );

    if (!targets.length) return;

    targets.forEach((target, index) => {
        target.classList.add("reveal-ready");
        target.style.transitionDelay = `${Math.min(index * 35, 260)}ms`;
    });

    const observer = new IntersectionObserver(
        (entries, obs) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("reveal-visible");
                obs.unobserve(entry.target);
            });
        },
        { threshold: 0.16, rootMargin: "0px 0px -50px 0px" }
    );

    targets.forEach((target) => observer.observe(target));
};

initHomeTabs();
animateHomeStats();
initScrollReveal();
