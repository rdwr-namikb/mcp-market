// Load server details when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, slug:', slug);
    loadServerDetails();
    setupTabs();
    setupShareButton();
    
    // Auto-load tools if Tools tab is active on page load
    const activeTab = document.querySelector('.tab-button.active');
    if (activeTab && activeTab.getAttribute('data-tab') === 'tools') {
        console.log('Tools tab is active, loading tools...');
        setTimeout(() => loadTools(), 500); // Small delay to ensure everything is ready
    }
});

// Load server details from API
async function loadServerDetails() {
    try {
        const response = await fetch(`/api/server/${slug}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading server:', data.error);
            document.getElementById('serverTitle').textContent = 'Server Not Found';
            return;
        }
        
        renderServerDetails(data);
    } catch (error) {
        console.error('Error fetching server details:', error);
        document.getElementById('serverTitle').textContent = 'Error Loading Server';
    }
}

// Render server details
function renderServerDetails(server) {
    // Update page title
    document.getElementById('pageTitle').textContent = `${server.full_name} - MCP Market`;
    
    // Update breadcrumb
    document.getElementById('breadcrumbName').textContent = server.full_name.split('/')[1] || server.full_name;
    
    // Update server icon with GitHub avatar
    const owner = server.full_name.split('/')[0] || '';
    const repoName = server.full_name.split('/')[1] || server.full_name;
    const avatarUrl = `https://github.com/${owner}.png?size=128`;
    const serverIcon = document.getElementById('serverIcon');
    
    // Clear existing content
    serverIcon.innerHTML = '';
    
    // Try to load GitHub avatar, fallback to first letter
    const img = document.createElement('img');
    img.src = avatarUrl;
    img.alt = owner;
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'cover';
    img.onerror = function() {
        // Fallback to first letter if image fails to load
        serverIcon.textContent = repoName.charAt(0).toUpperCase();
        serverIcon.style.display = 'flex';
        img.remove();
    };
    img.onload = function() {
        serverIcon.appendChild(img);
        serverIcon.style.display = 'flex';
    };
    
    // Update title
    document.getElementById('serverTitle').textContent = repoName;
    
    // Update author
    document.getElementById('serverOwner').textContent = server.owner || server.full_name.split('/')[0];
    
    // Update rating
    const starCount = formatNumber(server.stargazers_count || 0);
    document.getElementById('serverRating').textContent = starCount;
    
    // Update description
    document.getElementById('serverShortDesc').textContent = server.description || 'No description available';
    document.getElementById('aboutDescription').textContent = server.description || 'No description available.';
    
    // Update tags
    const tagsContainer = document.getElementById('serverTags');
    tagsContainer.innerHTML = '';
    
    // Add language tag if available
    if (server.language) {
        const langTag = document.createElement('span');
        langTag.className = 'tag';
        langTag.textContent = server.language;
        tagsContainer.appendChild(langTag);
    }
    
    // Add "Official" tag if it's from a well-known organization
    const officialOrgs = ['modelcontextprotocol', 'anthropic', 'openai'];
    if (officialOrgs.some(org => server.full_name.toLowerCase().includes(org))) {
        const officialTag = document.createElement('span');
        officialTag.className = 'tag official';
        officialTag.textContent = 'Official';
        tagsContainer.appendChild(officialTag);
    }
    
    // Add Developer Tools tag
    const devToolsTag = document.createElement('span');
    devToolsTag.className = 'tag';
    devToolsTag.textContent = 'Developer Tools';
    tagsContainer.appendChild(devToolsTag);
    
    // Update features list
    const featuresList = document.getElementById('featuresList');
    featuresList.innerHTML = '';
    
    const features = [
        `Access repository at ${server.html_url || `https://github.com/${server.full_name}`}`,
        `${formatNumber(server.stargazers_count || 0)} GitHub stars`,
        server.language ? `Written in ${server.language}` : 'Open source project',
        server.forks_count ? `${formatNumber(server.forks_count)} forks` : 'Active development',
    ];
    
    features.forEach(feature => {
        const li = document.createElement('li');
        li.textContent = feature;
        featuresList.appendChild(li);
    });
    
    // Update README content
    if (server.readme_content) {
        renderReadme(server.readme_content);
    } else {
        document.getElementById('readmeContent').innerHTML = '<p>README not available.</p>';
    }
    
    // Update GitHub link
    const githubBtn = document.getElementById('githubBtn');
    if (server.html_url) {
        githubBtn.href = server.html_url;
    } else {
        githubBtn.href = `https://github.com/${server.full_name}`;
    }
}

// Render README content (basic markdown rendering)
function renderReadme(content) {
    const readmeContainer = document.getElementById('readmeContent');
    
    // Simple markdown to HTML conversion (basic)
    let html = content
        // Headers
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Bold
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.*?)\*/gim, '<em>$1</em>')
        // Code blocks
        .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/gim, '<code>$1</code>')
        // Links
        .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        // Line breaks
        .replace(/\n\n/gim, '</p><p>')
        .replace(/\n/gim, '<br>');
    
    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }
    
    readmeContainer.innerHTML = html;
}

// Setup tab switching
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    let toolsLoaded = false; // Track if tools have been loaded
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            console.log('Tab clicked:', targetTab);
            
            // Remove active class from all buttons and panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            // Add active class to clicked button and corresponding pane
            button.classList.add('active');
            document.getElementById(`${targetTab}Tab`).classList.add('active');
            
            // Load tools if Tools tab is clicked and not already loaded
            if (targetTab === 'tools' && !toolsLoaded) {
                console.log('Loading tools...');
                toolsLoaded = true;
                loadTools();
            }
        });
    });
}

// Load tools from API
async function loadTools() {
    const toolsLoading = document.getElementById('toolsLoading');
    const toolsResults = document.getElementById('toolsResults');
    
    // Show loading indicator
    toolsLoading.style.display = 'block';
    toolsResults.innerHTML = '';
    
    try {
        const response = await fetch(`/api/server/${slug}/tools`);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
            toolsLoading.style.display = 'none';
            toolsResults.innerHTML = `<div class="tools-error"><p>Error: ${escapeHtml(errorData.error || 'HTTP ' + response.status)}</p></div>`;
            if (errorData.stderr) {
                toolsResults.innerHTML += `<pre class="tools-error-output">${escapeHtml(errorData.stderr)}</pre>`;
            }
            if (errorData.stdout) {
                toolsResults.innerHTML += `<pre class="tools-error-output">STDOUT: ${escapeHtml(errorData.stdout)}</pre>`;
            }
            console.error('Tools API error:', errorData);
            return;
        }
        
        const data = await response.json();
        
        toolsLoading.style.display = 'none';
        
        // Debug logging
        console.log('Tools API response:', data);
        
        if (data.error) {
            toolsResults.innerHTML = `<div class="tools-error"><p>Error: ${escapeHtml(data.error)}</p></div>`;
            if (data.stderr) {
                toolsResults.innerHTML += `<pre class="tools-error-output">${escapeHtml(data.stderr)}</pre>`;
            }
            if (data.debug) {
                toolsResults.innerHTML += `<pre class="tools-error-output">Debug: ${JSON.stringify(data.debug, null, 2)}</pre>`;
            }
            return;
        }
        
        if (!data.tools || data.tools.length === 0) {
            let message = '<div class="tools-empty"><p>No MCP tools were discovered in this repository.</p>';
            if (data.debug) {
                message += `<p style="font-size: 12px; color: #999; margin-top: 8px;">Debug: Found ${data.tools_count || 0} tools, output length: ${data.debug.output_length}</p>`;
            }
            message += '</div>';
            toolsResults.innerHTML = message;
            return;
        }
        
        // Render tools
        renderTools(data.tools, data.raw_output);
        
    } catch (error) {
        toolsLoading.style.display = 'none';
        console.error('Error loading tools:', error);
        toolsResults.innerHTML = `<div class="tools-error"><p>Error loading tools: ${escapeHtml(error.message)}</p><p style="font-size: 12px; color: #999;">Check browser console for details.</p></div>`;
    }
}

// Render tools list
function renderTools(tools, rawOutput) {
    const toolsResults = document.getElementById('toolsResults');
    
    console.log('Rendering tools:', tools);
    
    if (!tools || tools.length === 0) {
        toolsResults.innerHTML = '<div class="tools-empty"><p>No MCP tools were discovered in this repository.</p></div>';
        return;
    }
    
    let html = '<div class="tools-list">';
    html += `<h3 class="tools-heading">Discovered MCP Tools (${tools.length})</h3>`;
    
    tools.forEach((tool, index) => {
        console.log(`Rendering tool ${index + 1}:`, tool);
        html += '<div class="tool-item">';
        html += `<div class="tool-name">${escapeHtml(tool.name || 'Unnamed tool')}</div>`;
        if (tool.description) {
            // Convert newlines to <br> and preserve formatting
            const formattedDesc = escapeHtml(tool.description).replace(/\n/g, '<br>');
            html += `<div class="tool-description">${formattedDesc}</div>`;
        } else {
            html += '<div class="tool-description" style="color: #999; font-style: italic;">No description available</div>';
        }
        if (tool.origin) {
            html += `<div class="tool-origin">Declared in: <code>${escapeHtml(tool.origin)}</code></div>`;
        }
        html += '</div>';
    });
    
    html += '</div>';
    
    // Add raw output section (collapsible)
    if (rawOutput) {
        html += '<details class="tools-raw-output">';
        html += '<summary>View Raw Output</summary>';
        html += `<pre>${escapeHtml(rawOutput)}</pre>`;
        html += '</details>';
    }
    
    toolsResults.innerHTML = html;
    console.log('Tools rendered successfully');
}

// Utility to escape HTML for safe rendering
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

// Setup share button
function setupShareButton() {
    const shareBtn = document.getElementById('shareBtn');
    shareBtn.addEventListener('click', () => {
        if (navigator.share) {
            navigator.share({
                title: document.getElementById('serverTitle').textContent,
                text: document.getElementById('serverShortDesc').textContent,
                url: window.location.href
            });
        } else {
            // Fallback: copy to clipboard
            navigator.clipboard.writeText(window.location.href).then(() => {
                alert('Link copied to clipboard!');
            });
        }
    });
}

// Format large numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

