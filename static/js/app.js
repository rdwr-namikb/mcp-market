let currentPage = 1;
let isLoading = false;
let hasMore = true;
let currentSearch = '';
let searchTimeout = null;
const perPage = 12;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadServers();
    setupInfiniteScroll();
    setupExportButton();
    setupSearch();
});

// Load servers from API
async function loadServers() {
    if (isLoading || !hasMore) return;
    
    isLoading = true;
    const loadingEl = document.getElementById('loading');
    const endMessageEl = document.getElementById('endMessage');
    
    loadingEl.style.display = 'block';
    endMessageEl.style.display = 'none';
    
    try {
        const queryParams = new URLSearchParams({
            page: currentPage,
            per_page: perPage,
            search: currentSearch
        });
        
        const response = await fetch(`/api/servers?${queryParams}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading servers:', data.error);
            return;
        }
        
        if (data.servers && data.servers.length > 0) {
            renderServers(data.servers);
            currentPage++;
            hasMore = data.has_more;
        } else {
            hasMore = false;
            // Only show "no results" if it's the first page (search result empty)
            if (currentPage === 1) {
                // clear grid if it's a new search with no results
                // document.getElementById('serversGrid').innerHTML = '<p style="text-align:center; width:100%; grid-column: 1/-1;">No servers found matching your search.</p>';
            }
        }
        
        if (!hasMore) {
            loadingEl.style.display = 'none';
            endMessageEl.style.display = 'block';
            
            // Custom message for empty search results
            if (currentPage === 1 && (!data.servers || data.servers.length === 0)) {
                endMessageEl.querySelector('p').textContent = 'No servers found matching your search.';
            } else {
                endMessageEl.querySelector('p').textContent = "You've reached the end of the list!";
            }
        }
    } catch (error) {
        console.error('Error fetching servers:', error);
    } finally {
        isLoading = false;
        loadingEl.style.display = 'none';
    }
}

// Setup Search
function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const value = e.target.value.trim();
        
        // Debounce search
        if (searchTimeout) clearTimeout(searchTimeout);
        
        searchTimeout = setTimeout(() => {
            // Reset state for new search
            currentSearch = value;
            currentPage = 1;
            hasMore = true;
            document.getElementById('serversGrid').innerHTML = '';
            
            loadServers();
        }, 300);
    });
}

// Render server cards
function renderServers(servers) {
    const grid = document.getElementById('serversGrid');
    
    servers.forEach(server => {
        const card = createServerCard(server);
        grid.appendChild(card);
    });
}

// Create a server card element
function createServerCard(server) {
    const card = document.createElement('a');
    // Create URL-friendly slug from full_name
    const slug = server.full_name.replace('/', '-').toLowerCase();
    card.href = `/server/${slug}`;
    card.className = 'server-card';
    
    // Get owner and repo name
    const owner = server.full_name.split('/')[0] || '';
    const repoName = server.full_name.split('/')[1] || server.full_name;
    
    // Get GitHub avatar URL (GitHub provides avatars at this pattern)
    const avatarUrl = `https://github.com/${owner}.png?size=64`;
    
    // Format star count
    const starCount = formatNumber(server.stargazers_count || 0);
    
    // Truncate description if too long
    const description = server.description || 'No description available';
    
    card.innerHTML = `
        <div class="server-header">
            <div class="server-icon-container">
                <img src="${avatarUrl}" alt="${owner}" class="server-icon-img" onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="server-icon-fallback" style="display: none;">
                    ${repoName.charAt(0).toUpperCase()}
                </div>
            </div>
            <div class="server-info">
                <div class="server-name-row">
                    <div class="server-name">${escapeHtml(server.full_name)}</div>
                </div>
                <div class="server-rating">
                    <span class="star">★</span>
                    <span>${starCount}</span>
                </div>
            </div>
        </div>
        <div class="server-description">${escapeHtml(description)}</div>
    `;
    
    return card;
}

// Format large numbers (e.g., 1234 -> 1.2K)
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Setup infinite scroll
function setupInfiniteScroll() {
    window.addEventListener('scroll', () => {
        // Check if user scrolled near bottom of page
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        
        // Load more when user is 200px from bottom
        if (scrollTop + windowHeight >= documentHeight - 200) {
            loadServers();
        }
    });
}

// Setup export button
function setupExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn) return;
    
    exportBtn.addEventListener('click', async () => {
        if (exportBtn.disabled) return;
        const originalText = exportBtn.textContent;
        exportBtn.disabled = true;
        exportBtn.textContent = 'Exporting...';
        
        try {
            const response = await fetch('/api/servers/export');
            if (!response.ok) throw new Error('Failed to export CSV');
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'mcp_servers_top_100.csv';
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error exporting CSV:', error);
            alert('Failed to export CSV. Please try again.');
        } finally {
            exportBtn.disabled = false;
            exportBtn.textContent = originalText;
        }
    });
}

