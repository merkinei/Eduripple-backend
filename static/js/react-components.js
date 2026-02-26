// React/Preact Interactive Components Library
// Light alternative to full React for interactive elements

class InteractiveFeatureFilter {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.activeFilter = 'all';
        this.init();
    }

    init() {
        if (!this.container) return;
        
        // Add event listeners to filter buttons
        const filterButtons = this.container.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => this.handleFilterClick(btn));
        });
    }

    handleFilterClick(button) {
        const filterButtons = this.container.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.style.background = 'transparent';
            btn.style.color = 'var(--text-primary)';
            btn.style.borderColor = 'var(--border-color)';
        });

        button.style.background = 'var(--color-accent)';
        button.style.color = 'white';
        button.style.borderColor = 'var(--color-accent)';

        const filterValue = button.getAttribute('data-filter');
        this.activeFilter = filterValue;
        this.container.dispatchEvent(new CustomEvent('filterChange', { detail: { filter: filterValue } }));
    }
}

class AnimatedCounter {
    constructor(element, options = {}) {
        this.element = element;
        this.target = parseInt(element.getAttribute('data-target')) || 0;
        this.duration = options.duration || 2000;
        this.frameRate = options.frameRate || 16;
        this.isVisible = false;
        this.hasAnimated = false;
        this.setupObserver();
    }

    setupObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.hasAnimated) {
                    this.animate();
                    this.hasAnimated = true;
                }
            });
        }, { threshold: 0.5 });

        observer.observe(this.element);
    }

    animate() {
        const current = parseInt(this.element.textContent) || 0;
        const frames = this.duration / this.frameRate;
        const increment = (this.target - current) / frames;
        let frame = 0;

        const interval = setInterval(() => {
            frame++;
            const value = current + Math.round(increment * frame);
            this.element.textContent = value;

            if (frame >= frames) {
                this.element.textContent = this.target;
                clearInterval(interval);
            }
        }, this.frameRate);
    }
}

class ResourceLibraryManager {
    constructor(options = {}) {
        this.gridId = options.gridId || 'libraryGrid';
        this.searchId = options.searchId || 'librarySearch';
        this.filterPrefix = options.filterPrefix || 'filter-btn';
        this.resources = [];
        this.currentFilter = 'all';
        this.searchTerm = '';
        this.init();
    }

    async init() {
        await this.loadResources();
        this.setupEventListeners();
    }

    async loadResources() {
        try {
            const response = await fetch('/api/resources');
            const data = await response.json();
            this.resources = data.resources || [];
            this.render();
        } catch (error) {
            console.error('Failed to load resources:', error);
        }
    }

    setupEventListeners() {
        const searchInput = document.getElementById(this.searchId);
        const filterButtons = document.querySelectorAll(`.${this.filterPrefix}`);

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value.toLowerCase();
                this.render();
            });
        }

        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                this.currentFilter = btn.getAttribute('data-filter');
                this.updateFilterUI(btn);
                this.render();
            });
        });
    }

    updateFilterUI(activeButton) {
        const filterButtons = document.querySelectorAll(`.${this.filterPrefix}`);
        filterButtons.forEach(btn => {
            if (btn === activeButton) {
                btn.style.background = 'var(--color-accent)';
                btn.style.color = 'white';
                btn.style.borderColor = 'var(--color-accent)';
            } else {
                btn.style.background = 'transparent';
                btn.style.color = 'var(--text-primary)';
                btn.style.borderColor = 'var(--border-color)';
            }
        });
    }

    getResourceType(filename) {
        const lower = filename.toLowerCase();
        if (lower.includes('lesson') || lower.includes('plan')) {
            return { icon: '📘', type: 'lesson-plan', label: 'Lesson Plan' };
        } else if (lower.includes('scheme') || lower.includes('work')) {
            return { icon: '🗂️', type: 'scheme', label: 'Scheme of Work' };
        } else if (lower.includes('assessment') || lower.includes('rubric') || lower.includes('test')) {
            return { icon: '✅', type: 'assessment', label: 'Assessment' };
        }
        return { icon: '📄', type: 'other', label: 'Document' };
    }

    formatDate(isoString) {
        const date = new Date(isoString);
        return date.toLocaleDateString('en-KE', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
    }

    getFilteredResources() {
        let filtered = this.resources;

        if (this.currentFilter !== 'all') {
            filtered = filtered.filter(r => {
                const typeInfo = this.getResourceType(r.name);
                return typeInfo.type === this.currentFilter;
            });
        }

        if (this.searchTerm) {
            filtered = filtered.filter(r => 
                r.name.toLowerCase().includes(this.searchTerm)
            );
        }

        return filtered;
    }

    render() {
        const grid = document.getElementById(this.gridId);
        const filtered = this.getFilteredResources();

        if (filtered.length === 0) {
            grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 3rem 2rem;"><div style="font-size: 2rem; margin-bottom: 1rem;">🔍</div><p>No resources found. Try a different search or filter.</p></div>';
            return;
        }

        grid.innerHTML = filtered.map(resource => {
            const typeInfo = this.getResourceType(resource.name);
            const date = this.formatDate(resource.date);
            const size = this.formatFileSize(resource.size);
            const displayName = resource.name.replace(/\.[^/.]+$/, '');

            return `
                <div class="resource-card" data-filename="${resource.name}" style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.5rem; transition: all 0.3s ease; display: flex; flex-direction: column;">
                    <div class="resource-card-header" style="display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1rem;">
                        <span class="resource-icon" style="font-size: 2.5rem;">${typeInfo.icon}</span>
                        <div style="flex: 1;">
                            <h3 class="resource-title" style="margin: 0; font-size: 1.1rem; color: var(--text-primary); word-break: break-word;">${displayName}</h3>
                            <span style="font-size: 0.85rem; color: var(--color-accent); font-weight: 500;">${typeInfo.label}</span>
                        </div>
                    </div>
                    
                    <div class="resource-meta" style="display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; font-size: 0.9rem;">
                        <span style="display: flex; align-items: center; gap: 0.4rem; color: var(--text-secondary);">📅 ${date}</span>
                        <span style="display: flex; align-items: center; gap: 0.4rem; color: var(--text-secondary);">💾 ${size}</span>
                    </div>
                    
                    <div class="resource-actions" style="display: flex; gap: 0.75rem; margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                        <a href="/resources/${encodeURIComponent(resource.name)}" download style="flex: 1; padding: 0.6rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; background: var(--color-accent); color: white; text-decoration: none; text-align: center; transition: all 0.2s ease;">
                            ⬇️ Download
                        </a>
                        <button class="btn-delete" onclick="ResourceLibrary.deleteResource('${resource.name}', this)" style="flex: 1; padding: 0.6rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; background: #ffebee; color: #c62828; transition: all 0.2s ease;">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async deleteResource(filename, button) {
        if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;

        try {
            const response = await fetch('/teacher/delete-resource', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            });

            const data = await response.json();
            if (data.success) {
                this.resources = this.resources.filter(r => r.name !== filename);
                this.render();
            } else {
                alert('Failed to delete resource: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error deleting resource:', error);
            alert('Error deleting resource');
        }
    }
}

// Export for use in templates
window.ResourceLibraryManager = ResourceLibraryManager;
window.AnimatedCounter = AnimatedCounter;
window.InteractiveFeatureFilter = InteractiveFeatureFilter;
