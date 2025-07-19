/**
 * Neo4j Graph Visualization for SpiderFoot BE
 * 
 * Provides interactive graph visualization using D3.js for Neo4j data
 * Integrates with SpiderFoot's existing web interface
 */

class Neo4jVisualization {
    constructor(containerId, options = {}) {
        this.container = d3.select(`#${containerId}`);
        this.width = options.width || 800;
        this.height = options.height || 600;
        this.nodeRadius = options.nodeRadius || 8;
        this.linkDistance = options.linkDistance || 50;
        
        // Color scheme for different node types
        this.colorScheme = {
            'DOMAIN_NAME': '#1f77b4',
            'INTERNET_NAME': '#ff7f0e', 
            'EMAILADDR': '#2ca02c',
            'IP_ADDRESS': '#d62728',
            'URL': '#9467bd',
            'AFFILIATE_DOMAIN_NAME': '#8c564b',
            'AFFILIATE_INTERNET_NAME': '#e377c2',
            'default': '#7f7f7f'
        };
        
        this.simulation = null;
        this.nodes = [];
        this.links = [];
        this.nodeElements = null;
        this.linkElements = null;
        this.labelElements = null;
        
        this.initializeVisualization();
    }
    
    initializeVisualization() {
        // Clear existing content
        this.container.selectAll("*").remove();
        
        // Create SVG
        this.svg = this.container
            .append("svg")
            .attr("width", this.width)
            .attr("height", this.height)
            .call(d3.zoom().on("zoom", (event) => {
                this.g.attr("transform", event.transform);
            }));
            
        // Main group for zooming/panning
        this.g = this.svg.append("g");
        
        // Create groups for different elements (links first, then nodes)
        this.linkGroup = this.g.append("g").attr("class", "links");
        this.nodeGroup = this.g.append("g").attr("class", "nodes");
        this.labelGroup = this.g.append("g").attr("class", "labels");
        
        // Initialize force simulation
        this.simulation = d3.forceSimulation()
            .force("link", d3.forceLink().id(d => d.id).distance(this.linkDistance))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("center", d3.forceCenter(this.width / 2, this.height / 2))
            .force("collision", d3.forceCollide().radius(this.nodeRadius * 2))
            .on("tick", () => this.tick());
            
        // Add legend
        this.createLegend();
        
        // Add controls
        this.createControls();
    }
    
    async loadGraphData(scanId, nodeType = null, algorithm = 'pagerank') {
        try {
            // Fetch graph data from SpiderFoot API
            const response = await fetch(`/api/neo4j/graph/${scanId}?nodeType=${nodeType || ''}&algorithm=${algorithm}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.updateGraph(data.nodes, data.relationships);
            
            // Show statistics
            this.updateStatistics(data.statistics);
            
        } catch (error) {
            console.error('Failed to load graph data:', error);
            this.showError('Failed to load graph data: ' + error.message);
        }
    }
    
    updateGraph(nodes, links) {
        // Process nodes
        this.nodes = nodes.map(node => ({
            id: node.hash,
            label: node.data,
            type: node.type || 'default',
            confidence: node.confidence || 100,
            risk: node.risk || 0,
            scanned: node.scanned || false,
            affiliate: node.affiliate || false,
            x: Math.random() * this.width,
            y: Math.random() * this.height
        }));
        
        // Process links
        this.links = links.map(link => ({
            source: link.start,
            target: link.end,
            type: link.type,
            weight: link.weight || 1
        }));
        
        // Update visualization
        this.updateElements();
        this.restart();
    }
    
    updateElements() {
        // Update links
        this.linkElements = this.linkGroup
            .selectAll("line")
            .data(this.links);
            
        this.linkElements.exit().remove();
        
        this.linkElements = this.linkElements
            .enter()
            .append("line")
            .attr("class", "link")
            .attr("stroke", "#999")
            .attr("stroke-opacity", 0.6)
            .attr("stroke-width", d => Math.sqrt(d.weight))
            .merge(this.linkElements);
            
        // Update nodes
        this.nodeElements = this.nodeGroup
            .selectAll("circle")
            .data(this.nodes);
            
        this.nodeElements.exit().remove();
        
        const nodeEnter = this.nodeElements
            .enter()
            .append("circle")
            .attr("class", "node")
            .attr("r", this.nodeRadius)
            .attr("fill", d => this.getNodeColor(d))
            .attr("stroke", d => d.scanned ? "#000" : "#fff")
            .attr("stroke-width", d => d.scanned ? 2 : 1)
            .call(this.createDragBehavior())
            .on("click", (event, d) => this.onNodeClick(event, d))
            .on("mouseover", (event, d) => this.showTooltip(event, d))
            .on("mouseout", () => this.hideTooltip());
            
        this.nodeElements = nodeEnter.merge(this.nodeElements);
        
        // Update labels
        this.labelElements = this.labelGroup
            .selectAll("text")
            .data(this.nodes);
            
        this.labelElements.exit().remove();
        
        const labelEnter = this.labelElements
            .enter()
            .append("text")
            .attr("class", "label")
            .attr("font-size", "10px")
            .attr("font-family", "Arial, sans-serif")
            .attr("text-anchor", "middle")
            .attr("dy", ".35em")
            .text(d => this.truncateLabel(d.label));
            
        this.labelElements = labelEnter.merge(this.labelElements);
    }
    
    restart() {
        this.simulation.nodes(this.nodes);
        this.simulation.force("link").links(this.links);
        this.simulation.alpha(1).restart();
    }
    
    tick() {
        if (this.linkElements) {
            this.linkElements
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
        }
        
        if (this.nodeElements) {
            this.nodeElements
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
        }
        
        if (this.labelElements) {
            this.labelElements
                .attr("x", d => d.x)
                .attr("y", d => d.y + this.nodeRadius + 12);
        }
    }
    
    getNodeColor(node) {
        if (node.affiliate) {
            return this.colorScheme[`AFFILIATE_${node.type}`] || this.colorScheme.default;
        }
        return this.colorScheme[node.type] || this.colorScheme.default;
    }
    
    truncateLabel(label, maxLength = 20) {
        if (label.length <= maxLength) return label;
        return label.substring(0, maxLength - 3) + "...";
    }
    
    createDragBehavior() {
        return d3.drag()
            .on("start", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on("end", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }
    
    onNodeClick(event, node) {
        console.log('Node clicked:', node);
        
        // Highlight connected nodes
        this.highlightConnectedNodes(node);
        
        // Show detailed info panel
        this.showNodeDetails(node);
        
        // Emit custom event for integration with SpiderFoot UI
        const customEvent = new CustomEvent('neo4j-node-selected', {
            detail: { node: node }
        });
        document.dispatchEvent(customEvent);
    }
    
    highlightConnectedNodes(selectedNode) {
        // Reset all nodes
        this.nodeElements
            .attr("opacity", 0.3)
            .attr("stroke-width", 1);
            
        this.linkElements
            .attr("opacity", 0.1);
            
        // Highlight selected node
        this.nodeElements
            .filter(d => d.id === selectedNode.id)
            .attr("opacity", 1)
            .attr("stroke-width", 3);
            
        // Find connected nodes
        const connectedNodeIds = new Set();
        this.links.forEach(link => {
            if (link.source.id === selectedNode.id) {
                connectedNodeIds.add(link.target.id);
            }
            if (link.target.id === selectedNode.id) {
                connectedNodeIds.add(link.source.id);
            }
        });
        
        // Highlight connected nodes
        this.nodeElements
            .filter(d => connectedNodeIds.has(d.id))
            .attr("opacity", 0.8)
            .attr("stroke-width", 2);
            
        // Highlight connected links
        this.linkElements
            .filter(d => d.source.id === selectedNode.id || d.target.id === selectedNode.id)
            .attr("opacity", 0.8);
    }
    
    showTooltip(event, node) {
        const tooltip = d3.select("body")
            .append("div")
            .attr("class", "neo4j-tooltip")
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "8px")
            .style("border-radius", "4px")
            .style("font-size", "12px")
            .style("pointer-events", "none")
            .style("z-index", 1000);
            
        tooltip.html(`
            <div><strong>${node.label}</strong></div>
            <div>Type: ${node.type}</div>
            <div>Confidence: ${node.confidence}%</div>
            <div>Risk: ${node.risk}%</div>
            <div>Scanned: ${node.scanned ? 'Yes' : 'No'}</div>
            ${node.affiliate ? '<div>Affiliate: Yes</div>' : ''}
        `)
        .style("left", (event.pageX + 10) + "px")
        .style("top", (event.pageY - 10) + "px");
    }
    
    hideTooltip() {
        d3.selectAll(".neo4j-tooltip").remove();
    }
    
    showNodeDetails(node) {
        // Create or update details panel
        let detailsPanel = d3.select("#neo4j-details");
        
        if (detailsPanel.empty()) {
            detailsPanel = d3.select("body")
                .append("div")
                .attr("id", "neo4j-details")
                .style("position", "fixed")
                .style("right", "20px")
                .style("top", "20px")
                .style("width", "300px")
                .style("background", "white")
                .style("border", "1px solid #ccc")
                .style("border-radius", "8px")
                .style("padding", "15px")
                .style("box-shadow", "0 4px 6px rgba(0, 0, 0, 0.1)")
                .style("z-index", 1001);
                
            // Add close button
            detailsPanel.append("button")
                .text("×")
                .style("float", "right")
                .style("border", "none")
                .style("background", "none")
                .style("font-size", "18px")
                .style("cursor", "pointer")
                .on("click", () => detailsPanel.remove());
        }
        
        detailsPanel.html(`
            <button style="float: right; border: none; background: none; font-size: 18px; cursor: pointer;" onclick="this.parentElement.remove()">×</button>
            <h3 style="margin-top: 0;">Node Details</h3>
            <div><strong>Data:</strong> ${node.label}</div>
            <div><strong>Type:</strong> ${node.type}</div>
            <div><strong>Confidence:</strong> ${node.confidence}%</div>
            <div><strong>Risk:</strong> ${node.risk}%</div>
            <div><strong>Scanned:</strong> ${node.scanned ? 'Yes' : 'No'}</div>
            ${node.affiliate ? '<div><strong>Affiliate:</strong> Yes</div>' : ''}
            <hr>
            <button onclick="neo4jViz.expandNode('${node.id}')" style="margin: 5px;">Expand</button>
            <button onclick="neo4jViz.hideNode('${node.id}')" style="margin: 5px;">Hide</button>
            <button onclick="neo4jViz.focusNode('${node.id}')" style="margin: 5px;">Focus</button>
        `);
    }
    
    createLegend() {
        const legend = this.svg.append("g")
            .attr("class", "legend")
            .attr("transform", `translate(20, ${this.height - 150})`);
            
        const legendItems = Object.entries(this.colorScheme)
            .filter(([key]) => key !== 'default')
            .slice(0, 6); // Show top 6 types
            
        const legendItem = legend.selectAll(".legend-item")
            .data(legendItems)
            .enter()
            .append("g")
            .attr("class", "legend-item")
            .attr("transform", (d, i) => `translate(0, ${i * 20})`);
            
        legendItem.append("circle")
            .attr("r", 6)
            .attr("fill", d => d[1]);
            
        legendItem.append("text")
            .attr("x", 15)
            .attr("y", 0)
            .attr("dy", ".35em")
            .style("font-size", "12px")
            .text(d => d[0].replace('_', ' '));
    }
    
    createControls() {
        const controls = this.container
            .append("div")
            .attr("class", "neo4j-controls")
            .style("margin-top", "10px");
            
        // Algorithm selector
        controls.append("label")
            .text("Algorithm: ")
            .append("select")
            .attr("id", "algorithm-select")
            .on("change", () => this.onAlgorithmChange())
            .selectAll("option")
            .data(['pagerank', 'betweenness', 'closeness'])
            .enter()
            .append("option")
            .attr("value", d => d)
            .text(d => d.charAt(0).toUpperCase() + d.slice(1));
            
        // Node type filter
        controls.append("label")
            .style("margin-left", "20px")
            .text("Node Type: ")
            .append("select")
            .attr("id", "nodetype-select")
            .on("change", () => this.onNodeTypeChange())
            .selectAll("option")
            .data(['All', 'DOMAIN_NAME', 'INTERNET_NAME', 'EMAILADDR', 'IP_ADDRESS'])
            .enter()
            .append("option")
            .attr("value", d => d === 'All' ? '' : d)
            .text(d => d);
            
        // Refresh button
        controls.append("button")
            .style("margin-left", "20px")
            .text("Refresh")
            .on("click", () => this.refresh());
            
        // Reset zoom button
        controls.append("button")
            .style("margin-left", "10px")
            .text("Reset Zoom")
            .on("click", () => this.resetZoom());
    }
    
    onAlgorithmChange() {
        const algorithm = d3.select("#algorithm-select").node().value;
        const scanId = this.getCurrentScanId();
        if (scanId) {
            this.loadGraphData(scanId, null, algorithm);
        }
    }
    
    onNodeTypeChange() {
        const nodeType = d3.select("#nodetype-select").node().value;
        const scanId = this.getCurrentScanId();
        if (scanId) {
            this.loadGraphData(scanId, nodeType);
        }
    }
    
    refresh() {
        const scanId = this.getCurrentScanId();
        if (scanId) {
            this.loadGraphData(scanId);
        }
    }
    
    resetZoom() {
        this.svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
    }
    
    expandNode(nodeId) {
        // Load additional connected nodes
        console.log('Expanding node:', nodeId);
        // Implementation would fetch additional relationships
    }
    
    hideNode(nodeId) {
        // Hide node and its connections
        this.nodes = this.nodes.filter(n => n.id !== nodeId);
        this.links = this.links.filter(l => l.source.id !== nodeId && l.target.id !== nodeId);
        this.updateElements();
        this.restart();
    }
    
    focusNode(nodeId) {
        const node = this.nodes.find(n => n.id === nodeId);
        if (node) {
            const transform = d3.zoomIdentity
                .translate(this.width / 2 - node.x, this.height / 2 - node.y)
                .scale(2);
                
            this.svg.transition().duration(750).call(
                d3.zoom().transform,
                transform
            );
        }
    }
    
    getCurrentScanId() {
        // Extract scan ID from current page URL or context
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('id') || window.currentScanId;
    }
    
    updateStatistics(stats) {
        // Update statistics display
        const statsContainer = d3.select("#neo4j-stats");
        if (!statsContainer.empty()) {
            statsContainer.html(`
                <div><strong>Nodes:</strong> ${stats.nodes || 0}</div>
                <div><strong>Relationships:</strong> ${stats.relationships || 0}</div>
                <div><strong>Events Streamed:</strong> ${stats.events_streamed || 0}</div>
            `);
        }
    }
    
    showError(message) {
        const errorDiv = d3.select("body")
            .append("div")
            .attr("class", "neo4j-error")
            .style("position", "fixed")
            .style("top", "20px")
            .style("left", "50%")
            .style("transform", "translateX(-50%)")
            .style("background", "#ff4444")
            .style("color", "white")
            .style("padding", "10px 20px")
            .style("border-radius", "4px")
            .style("z-index", 2000)
            .text(message);
            
        setTimeout(() => errorDiv.remove(), 5000);
    }
}

// Global instance for external access
let neo4jViz = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('neo4j-graph-container')) {
        neo4jViz = new Neo4jVisualization('neo4j-graph-container', {
            width: 1000,
            height: 700
        });
        
        // Auto-load if scan ID is available
        const scanId = neo4jViz.getCurrentScanId();
        if (scanId) {
            neo4jViz.loadGraphData(scanId);
        }
    }
});