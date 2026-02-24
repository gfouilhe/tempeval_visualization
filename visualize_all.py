#!/usr/bin/env python3
"""
Multi-file TempEval Visualization

Generates a single HTML page with all TML files visualized in tabs.
Creates a fully offline version with embedded D3.js library.

Usage:
    python visualize_all.py data/taskAB/
    python visualize_all.py data/taskAB/ data/taskC/
    python visualize_all.py data/taskAB/ --output all_files.html
    python visualize_all.py data/taskAB/ data/taskC/ --limit 10  # Only first 10 files
"""
 
import xml.etree.ElementTree as ET
import argparse
import sys
import os
from pathlib import Path
from collections import Counter
import json


class TempEvalParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.events = {}
        self.timexes = {}
        self.tlinks = []
        self.sentences = []
        self.raw_xml = None
        self.parse_file()
    
    def parse_file(self):
        """Parse the TML file and extract annotations"""
        try:
            # Read raw XML content
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.raw_xml = f.read()
            
            tree = ET.parse(self.filepath)
            root = tree.getroot()
            
            # Extract events
            for event in root.findall('.//EVENT'):
                eid = event.get('eid')
                self.events[eid] = {
                    'text': event.text or '',
                    'class': event.get('class'),
                    'tense': event.get('tense'),
                    'aspect': event.get('aspect'),
                    'polarity': event.get('polarity'),
                    'pos': event.get('pos'),
                    'stem': event.get('stem'),
                    'mainevent': event.get('mainevent')
                }
            
            # Extract time expressions
            for timex in root.findall('.//TIMEX3'):
                tid = timex.get('tid')
                self.timexes[tid] = {
                    'text': timex.text or '',
                    'type': timex.get('type'),
                    'value': timex.get('value'),
                    'functionInDocument': timex.get('functionInDocument')
                }
            
            # Extract temporal links
            for tlink in root.findall('.//TLINK'):
                self.tlinks.append({
                    'lid': tlink.get('lid'),
                    'relType': tlink.get('relType'),
                    'eventID': tlink.get('eventID'),
                    'timeID': tlink.get('timeID'),
                    'relatedToEvent': tlink.get('relatedToEvent'),
                    'relatedToTime': tlink.get('relatedToTime'),
                    'task': tlink.get('task')
                })
            
            # Extract sentences
            for sentence in root.findall('.//s'):
                self.sentences.append(self._render_sentence(sentence))
                
        except Exception as e:
            print(f"Error parsing {self.filepath}: {e}")
    
    def _render_sentence(self, elem):
        """Render sentence to text with annotations"""
        result = []
        
        if elem.text:
            result.append(elem.text)
        
        for child in elem:
            if child.tag == 'EVENT':
                eid = child.get('eid')
                text = child.text or ''
                event_class = self.events.get(eid, {}).get('class', '')
                title = f"ID: {eid}, Class: {event_class}"
                result.append(f'<span class="event" data-id="{eid}" title="{title}">{text}</span>')
                result.append(f'<span class="event-id">[{eid}]</span>')
            elif child.tag == 'TIMEX3':
                tid = child.get('tid')
                text = child.text or ''
                timex_value = self.timexes.get(tid, {}).get('value', '')
                title = f"ID: {tid}, Value: {timex_value}"
                result.append(f'<span class="timex" data-id="{tid}" title="{title}">{text}</span>')
                result.append(f'<span class="timex-id">[{tid}]</span>')
            
            if child.tail:
                result.append(child.tail)
        
        return ''.join(result)
    
    def get_plain_text(self):
        """Extract plain text without any XML tags"""
        plain_text = []
        try:
            tree = ET.parse(self.filepath)
            root = tree.getroot()
            for sentence in root.findall('.//s'):
                sentence_text = []
                if sentence.text:
                    sentence_text.append(sentence.text)
                for child in sentence:
                    if child.text:
                        sentence_text.append(child.text)
                    if child.tail:
                        sentence_text.append(child.tail)
                plain_text.append(''.join(sentence_text).strip())
        except Exception:
            pass
        return '\n'.join(plain_text)
    
    def get_graph_data(self):
        """Get nodes and links for graph"""
        nodes = []
        node_ids = {}
        
        for eid, event in self.events.items():
            node_ids[eid] = len(nodes)
            nodes.append({
                'id': eid,
                'label': event['text'][:15],
                'type': 'event',
                'fullText': event['text'],
                'class': event['class']
            })
        
        for tid, timex in self.timexes.items():
            node_ids[tid] = len(nodes)
            nodes.append({
                'id': tid,
                'label': timex['text'][:15],
                'type': 'timex',
                'fullText': timex['text'],
                'value': timex['value']
            })
        
        links = []
        for tlink in self.tlinks:
            src = tlink['eventID'] or tlink['timeID']
            tgt = tlink['relatedToEvent'] or tlink['relatedToTime']
            
            if src and tgt and src in node_ids and tgt in node_ids:
                links.append({
                    'source': node_ids[src],
                    'target': node_ids[tgt],
                    'relation': tlink['relType'],
                    'sourceId': src,
                    'targetId': tgt
                })
        
        return nodes, links


def generate_multi_file_html(files, output_path):
    """Generate HTML with all files in tabs"""
    
    print(f"Processing {len(files)} files...")
    all_data = []
    
    # Track which tasks exist across all files
    global_tasks = set()
    
    for i, filepath in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {filepath.name}")
        parser = TempEvalParser(str(filepath))
        nodes, links = parser.get_graph_data()
        
        # Count tasks
        tasks = set()
        task_counts = {'A': 0, 'B': 0, 'C': 0}
        for tlink in parser.tlinks:
            task = tlink.get('task')
            if task:
                tasks.add(task)
                global_tasks.add(task)
                task_counts[task] = task_counts.get(task, 0) + 1
        
        all_data.append({
            'filename': filepath.name,
            'filepath': str(filepath),
            'events': len(parser.events),
            'timexes': len(parser.timexes),
            'tlinks': len(parser.tlinks),
            'sentences': parser.sentences,
            'nodes': nodes,
            'links': links,
            'tasks': ','.join(sorted(tasks)),
            'task_counts': task_counts,
            'plain_text': parser.get_plain_text(),
            'raw_xml': parser.raw_xml or ''
        })
    
    # Calculate overall statistics
    total_events = sum(d['events'] for d in all_data)
    total_timexes = sum(d['timexes'] for d in all_data)
    total_tlinks = sum(d['tlinks'] for d in all_data)
    
    # Read D3.js library for embedding
    d3_js = ""
    d3_path = Path(__file__).parent / 'd3.v7.min.js'
    if d3_path.exists():
        with open(d3_path, 'r', encoding='utf-8') as f:
            d3_js = f.read()
        print(f"  Embedding D3.js library ({len(d3_js)} bytes) - fully offline version")
    else:
        print(f"  Warning: d3.v7.min.js not found, using CDN (requires internet)")
        d3_js = None
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TempEval Visualization - {len(files)} files</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        .tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            background-color: white;
            padding: 15px;
            border-radius: 8px 8px 0 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
            max-height: 150px;
            overflow-y: auto;
        }}
        .tab {{
            padding: 10px 20px;
            background-color: #ecf0f1;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
            white-space: nowrap;
        }}
        .tab:hover {{
            background-color: #d5dbdb;
        }}
        .tab.active {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        .tab-content {{
            display: none;
            background-color: white;
            padding: 30px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .tab-content.active {{
            display: block;
        }}
        .file-header {{
            border-bottom: 2px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .file-stats {{
            display: flex;
            gap: 30px;
            margin-top: 10px;
            flex-wrap: wrap;
        }}
        .file-stat {{
            font-size: 14px;
            color: #7f8c8d;
        }}
        .file-stat strong {{
            color: #2c3e50;
            font-size: 18px;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section h3 {{
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .graph-container {{
            width: 100%;
            height: 500px;
            border: 1px solid #ddd;
            background-color: #fafafa;
            margin: 15px 0;
            position: relative;
        }}
        .graph-controls {{
            margin: 10px 0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .graph-controls button {{
            padding: 8px 16px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .graph-controls button:hover {{
            background-color: #2980b9;
        }}
        .relation-legend {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 12px;
            margin: 10px 0;
            font-size: 13px;
        }}
        .relation-legend h4 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #2c3e50;
        }}
        .legend-items {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 30px;
            height: 3px;
            border-radius: 1px;
        }}
        .legend-label {{
            font-weight: 600;
            color: #34495e;
        }}
        .legend-description {{
            color: #7f8c8d;
            font-size: 12px;
        }}
        .sentence {{
            line-height: 1.8;
            margin-bottom: 12px;
            padding: 12px;
            background-color: #f8f9fa;
            border-left: 3px solid #3498db;
            border-radius: 3px;
        }}
        .event {{
            background-color: #3498db;
            color: white;
            padding: 2px 5px;
            border-radius: 3px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .event:hover {{
            background-color: #2980b9;
            transform: scale(1.05);
        }}
        .timex {{
            background-color: #2ecc71;
            color: white;
            padding: 2px 5px;
            border-radius: 3px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .timex:hover {{
            background-color: #27ae60;
            transform: scale(1.05);
        }}
        .node-highlighted circle,
        .node-highlighted rect {{
            stroke: #f39c12 !important;
            stroke-width: 4 !important;
            filter: drop-shadow(0 0 8px #f39c12);
        }}
        .relations-list {{
            margin-top: 10px;
        }}
        .relation-item {{
            padding: 10px;
            margin: 8px 0;
            background-color: #f8f9fa;
            border-left: 4px solid #95a5a6;
            border-radius: 3px;
            font-size: 14px;
            line-height: 1.6;
        }}
        .relation-item.BEFORE {{ border-left-color: #e74c3c; }}
        .relation-item.AFTER {{ border-left-color: #9b59b6; }}
        .relation-item.OVERLAP {{ border-left-color: #f39c12; }}
        .relation-item.BEFORE-OR-OVERLAP {{ border-left-color: #16a085; }}
        .relation-item.OVERLAP-OR-AFTER {{ border-left-color: #d35400; }}
        .relation-item.VAGUE {{ border-left-color: #95a5a6; }}
        .relation-arrow {{
            color: #7f8c8d;
            font-weight: bold;
            margin: 0 8px;
        }}
        .relation-type {{
            font-weight: bold;
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            color: white;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .relation-type.BEFORE {{ background-color: #e74c3c; }}
        .relation-type.AFTER {{ background-color: #9b59b6; }}
        .relation-type.OVERLAP {{ background-color: #f39c12; }}
        .relation-type.BEFORE-OR-OVERLAP {{ background-color: #16a085; }}
        .relation-type.OVERLAP-OR-AFTER {{ background-color: #d35400; }}
        .relation-type.VAGUE {{ background-color: #95a5a6; }}
        .event-id, .timex-id {{
            font-size: 0.85em;
            color: #7f8c8d;
            font-weight: normal;
            margin-left: 2px;
        }}
        .search-box {{
            margin: 20px 0;
            padding: 15px;
            background-color: #ecf0f1;
            border-radius: 5px;
        }}
        .search-box input {{
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }}
        .filter-controls {{
            margin: 20px 0;
            padding: 15px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .filter-controls h3 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 16px;
        }}
        .filter-row {{
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-group label {{
            font-size: 14px;
            color: #555;
            white-space: nowrap;
        }}
        .filter-group select {{
            padding: 6px 12px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-size: 14px;
            background-color: white;
            cursor: pointer;
        }}
        .filter-group button {{
            padding: 6px 12px;
            background-color: #95a5a6;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .filter-group button:hover {{
            background-color: #7f8c8d;
        }}
        .no-graph {{
            text-align: center;
            padding: 50px;
            color: #95a5a6;
        }}
        .export-button {{
            padding: 12px 24px;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.2s;
        }}
        .export-button:nth-child(1) {{
            background-color: #3498db;
        }}
        .export-button:nth-child(2) {{
            background-color: #2ecc71;
        }}
        .export-button:nth-child(3) {{
            background-color: #27ae60;
        }}
        .export-button:hover {{
            opacity: 0.9;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            overflow: auto;
        }}
        .modal-content {{
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            width: 90%;
            max-width: 1000px;
            border-radius: 5px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .modal-close {{
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            color: #aaa;
        }}
        .modal-close:hover {{
            color: #000;
        }}
        .credits {{
            background-color: #ecf0f1;
            padding: 15px;
            margin: 20px;
            border-radius: 5px;
            border-left: 4px solid #667eea;
            font-size: 14px;
            color: #2c3e50;
            text-align: center;
        }}
        .credits a {{
            color: #667eea;
            text-decoration: none;
            font-weight: bold;
        }}
        .credits a:hover {{
            text-decoration: underline;
        }}
    </style>
    <script>
{d3_js if d3_js else ""}
    </script>
    {"" if d3_js else '<script src="https://d3js.org/d3.v7.min.js"></script>'}
</head>
<body>
    <div id="rawXmlModal" class="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeRawXML()">&times;</span>
            <h2>Raw XML Content</h2>
            <pre style="background-color: #f5f5f5; padding: 15px; border-radius: 3px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; font-size: 12px; line-height: 1.4;"><code id="rawXmlContent"></code></pre>
        </div>
    </div>
    
    <div class="header">
        <h1>📊 TempEval Visualization</h1>
        <p>Viewing {len(files)} annotated documents</p>
    </div>
    
    <div class="credits">
        📚 <strong>Data Source:</strong> This visualization uses data from <a href="https://timeml.github.io/site/timebank/timebank.html" target="_blank">TimeBank</a>, 
        a corpus annotated with <a href="https://timeml.github.io/site/index.html" target="_blank">TimeML</a> temporal markup language. 
    </div>
    
    <div class="header">
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-number">{len(files)}</div>
                <div class="stat-label">Files</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{total_events}</div>
                <div class="stat-label">Total Events</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{total_timexes}</div>
                <div class="stat-label">Total Time Expressions</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{total_tlinks}</div>
                <div class="stat-label">Total Temporal Links</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="search-box">
            <input type="text" id="search" placeholder="🔍 Search files by name..." oninput="applyFilters()">
        </div>
        
        <div class="filter-controls">
            <h3>📊 Sort & Filter</h3>
            <div class="filter-row">
                <div class="filter-group">
                    <label for="sortBy">Sort by:</label>
                    <select id="sortBy" onchange="applyFilters()">
                        <option value="filename">Filename (A-Z)</option>
                        <option value="filename-desc">Filename (Z-A)</option>
                        <option value="events-desc">Events (Most first)</option>
                        <option value="events-asc">Events (Least first)</option>
                        <option value="timexes-desc">Time Expressions (Most first)</option>
                        <option value="timexes-asc">Time Expressions (Least first)</option>
                        <option value="tlinks-desc">Temporal Links (Most first)</option>
                        <option value="tlinks-asc">Temporal Links (Least first)</option>
                        <option value="sentences-desc">Sentences (Most first)</option>
                        <option value="sentences-asc">Sentences (Least first)</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="taskFilter">Task:</label>
                    <select id="taskFilter" onchange="applyFilters()">
                        <option value="all">All Tasks</option>
                        <option value="A">Task A only</option>
                        <option value="B">Task B only</option>
                        <option value="C">Task C only</option>
                        <option value="AB">Tasks A & B</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="minEvents">Min Events:</label>
                    <select id="minEvents" onchange="applyFilters()">
                        <option value="0">All</option>
                        <option value="10">10+</option>
                        <option value="20">20+</option>
                        <option value="30">30+</option>
                        <option value="50">50+</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="minLinks">Min Links:</label>
                    <select id="minLinks" onchange="applyFilters()">
                        <option value="0">All</option>
                        <option value="5">5+</option>
                        <option value="10">10+</option>
                        <option value="20">20+</option>
                        <option value="30">30+</option>
                    </select>
                </div>
                <div class="filter-group">
                    <button onclick="resetFilters()">Reset All</button>
                </div>
                <div class="filter-group">
                    <span id="matchCount" style="color: #7f8c8d; font-size: 14px;"></span>
                </div>
            </div>
        </div>
        
        <div class="tabs" id="tabs">
"""
    
    # Generate tabs
    for i, data in enumerate(all_data):
        active = ' active' if i == 0 else ''
        tasks_str = data['tasks'] if data['tasks'] else 'none'
        html += f'            <button class="tab{active}" onclick="showTab({i})" data-index="{i}" data-filename="{data["filename"]}" data-events="{data["events"]}" data-timexes="{data["timexes"]}" data-tlinks="{data["tlinks"]}" data-sentences="{len(data["sentences"])}" data-tasks="{tasks_str}">{data["filename"]}</button>\n'
    
    html += """        </div>
        
"""
    
    # Generate tab contents
    for i, data in enumerate(all_data):
        active = ' active' if i == 0 else ''
        # Only show tasks that exist in the dataset
        task_parts = []
        for task in sorted(global_tasks):
            count = data['task_counts'].get(task, 0)
            task_parts.append(f"Task {task}: <strong>{count}</strong>")
        task_info = f"<div class=\"file-stat\">{' | '.join(task_parts)}</div>" if task_parts else ""
        
        html += f"""        <div class="tab-content{active}" id="tab-{i}">
            <div class="file-header">
                <h2>{data['filename']}</h2>
                <div class="file-stats">
                    <div class="file-stat">Events: <strong>{data['events']}</strong></div>
                    <div class="file-stat">Time Expressions: <strong>{data['timexes']}</strong></div>
                    <div class="file-stat">Temporal Links: <strong>{data['tlinks']}</strong></div>
                    <div class="file-stat">Sentences: <strong>{len(data['sentences'])}</strong></div>
                    {task_info}
                </div>
            </div>
"""
        
        # Graph section
        if data['nodes']:
            html += f"""            
            <div class="section">
                <h3>Temporal Relations Graph</h3>
                <div class="relation-legend">
                    <h4>Temporal Relations Legend</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #e74c3c;"></div>
                            <div>
                                <div class="legend-label">BEFORE</div>
                                <div class="legend-description">Source → Target: Source occurs before target</div>
                            </div>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #9b59b6;"></div>
                            <div>
                                <div class="legend-label">AFTER</div>
                                <div class="legend-description">Source → Target: Source occurs after target</div>
                            </div>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #f39c12;"></div>
                            <div>
                                <div class="legend-label">OVERLAP</div>
                                <div class="legend-description">Source → Target: Events overlap in time</div>
                            </div>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #16a085;"></div>
                            <div>
                                <div class="legend-label">BEFORE-OR-OVERLAP</div>
                                <div class="legend-description">Source → Target: Before or overlapping (ambiguous)</div>
                            </div>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #d35400;"></div>
                            <div>
                                <div class="legend-label">OVERLAP-OR-AFTER</div>
                                <div class="legend-description">Source → Target: Overlapping or after (ambiguous)</div>
                            </div>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color" style="background-color: #95a5a6;"></div>
                            <div>
                                <div class="legend-label">VAGUE</div>
                                <div class="legend-description">Source → Target: Temporal relationship is unclear</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="graph-controls">
                    <button onclick="resetGraph({i})">Reset</button>
                    <button onclick="fitToView({i})">Fit to View</button>
                    <button onclick="zoomIn({i})">Zoom In</button>
                    <button onclick="zoomOut({i})">Zoom Out</button>
                    <button onclick="toggleGraphLabels({i})">Toggle ID/Text</button>
                    <span id="label-status-{i}" style="margin-left: 10px; color: #7f8c8d;">Labels: ID</span>
                </div>
                <div class="graph-container" id="graph-{i}"></div>
            </div>
"""
        else:
            html += '            <div class="no-graph">No temporal relations to display</div>\n'
        
        # Text section
        html += f"""            <div class="section" id="text-section-{i}">
                <h3>Annotated Text</h3>
"""
        for j, sentence in enumerate(data['sentences'], 1):
            html += f'                <div class="sentence"><strong>{j}.</strong> {sentence}</div>\n'
        
        html += f"""            </div>
            
            <div class="section">
                <h3>Temporal Relations ({len(data['links'])})</h3>
                <div class="relations-list">
"""
        
        # Add temporal relations with actual text
        if data['links']:
            # Create a lookup for node text
            node_lookup = {node['id']: node for node in data['nodes']}
            
            for link in data['links']:
                relation_type = link['relation']
                source_id = link['sourceId']
                target_id = link['targetId']
                
                # Get source and target text
                source_node = node_lookup.get(source_id, {})
                target_node = node_lookup.get(target_id, {})
                source_text = source_node.get('fullText', source_id)
                target_text = target_node.get('fullText', target_id)
                
                # Truncate long text
                if len(source_text) > 30:
                    source_text = source_text[:27] + '...'
                if len(target_text) > 30:
                    target_text = target_text[:27] + '...'
                
                html += f'''                    <div class="relation-item {relation_type}">
                        <span class="relation-type {relation_type}">{relation_type}</span>
                        <div style="display: inline-block; margin-left: 10px;">
                            <strong>{source_id}</strong> <span style="color: #7f8c8d; font-size: 12px;">({source_text})</span>
                            <span class="relation-arrow">→</span>
                            <strong>{target_id}</strong> <span style="color: #7f8c8d; font-size: 12px;">({target_text})</span>
                        </div>
                    </div>
'''
        else:
            html += '                    <p style="color: #7f8c8d;">No temporal relations in this file.</p>\n'
        
        html += f"""                </div>
            </div>
            
            <div class="section">
                <h3>Export Options</h3>
                <div style="display: flex; gap: 15px; margin-top: 20px;">
                    <button onclick="downloadPlainText({i})" class="export-button">
                        📄 Download Plain Text
                    </button>
                    <button onclick="viewRawXML({i})" class="export-button">
                        📋 View Raw XML
                    </button>
                    <button onclick="downloadRawXML({i})" class="export-button">
                        💾 Download Raw XML
                    </button>
                </div>
            </div>
        </div>
        
"""
    
    html += """    </div>
    
    <script>
        // Store all graph data
        const allGraphData = """ + json.dumps([{'nodes': d['nodes'], 'links': d['links']} for d in all_data]) + """;
        const graphInstances = {};
        
        // Store plain text and raw XML data
        const allPlainTextData = """ + json.dumps([d['plain_text'] for d in all_data], ensure_ascii=False) + """;
        const allRawXmlData = """ + json.dumps([d['raw_xml'] for d in all_data], ensure_ascii=False) + """;
        const allFilenames = """ + json.dumps([d['filename'] for d in all_data]) + """;
        
        console.log('Data loaded:', allFilenames.length + ' files');
        
        function downloadPlainText(index) {
            try {
                console.log('Downloading plain text for file', index, ':', allFilenames[index]);
                const text = allPlainTextData[index];
                const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = allFilenames[index].replace('.tml', '_plain.txt');
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (e) {
                console.error('Error downloading plain text:', e);
                alert('Error downloading plain text: ' + e.message);
            }
        }
        
        function viewRawXML(index) {
            try {
                console.log('Viewing raw XML for file', index, ':', allFilenames[index]);
                document.getElementById('rawXmlContent').textContent = allRawXmlData[index];
                document.getElementById('rawXmlModal').style.display = 'block';
            } catch (e) {
                console.error('Error viewing raw XML:', e);
                alert('Error viewing raw XML: ' + e.message);
            }
        }
        
        function closeRawXML() {
            document.getElementById('rawXmlModal').style.display = 'none';
        }
        
        function downloadRawXML(index) {
            try {
                console.log('Downloading raw XML for file', index, ':', allFilenames[index]);
                const xml = allRawXmlData[index];
                const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = allFilenames[index];
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (e) {
                console.error('Error downloading raw XML:', e);
                alert('Error downloading raw XML: ' + e.message);
            }
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('rawXmlModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        }
        
        function showTab(index) {
            // Hide all tabs
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Show selected tab
            const tabs = document.querySelectorAll('.tab');
            const tabToActivate = Array.from(tabs).find(t => parseInt(t.getAttribute('data-index')) === index);
            if (tabToActivate) {
                tabToActivate.classList.add('active');
                tabToActivate.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            document.getElementById(`tab-${index}`).classList.add('active');
            
            // Initialize graph if not already done
            if (!graphInstances[index] && allGraphData[index].nodes.length > 0) {
                initGraph(index);
            }
        }
        
        function applyFilters() {
            const search = document.getElementById('search').value.toLowerCase();
            const sortBy = document.getElementById('sortBy').value;
            const minEvents = parseInt(document.getElementById('minEvents').value);
            const minLinks = parseInt(document.getElementById('minLinks').value);
            const taskFilter = document.getElementById('taskFilter').value;
            
            const tabs = Array.from(document.querySelectorAll('.tab'));
            
            // Filter tabs
            let visibleTabs = tabs.filter(tab => {
                const filename = tab.getAttribute('data-filename').toLowerCase();
                const events = parseInt(tab.getAttribute('data-events'));
                const tlinks = parseInt(tab.getAttribute('data-tlinks'));
                const tasks = tab.getAttribute('data-tasks') || 'none';
                
                // Apply search filter
                if (!filename.includes(search)) return false;
                
                // Apply numeric filters
                if (events < minEvents) return false;
                if (tlinks < minLinks) return false;
                
                // Apply task filter
                if (taskFilter !== 'all') {
                    if (tasks === 'none') return false;
                    
                    const fileTasks = tasks.split(',');
                    
                    if (taskFilter === 'A' || taskFilter === 'B' || taskFilter === 'C') {
                        // Single task - must have this task
                        if (!fileTasks.includes(taskFilter)) return false;
                    } else if (taskFilter === 'AB') {
                        // Tasks A & B - must have both
                        if (!fileTasks.includes('A') || !fileTasks.includes('B')) return false;
                    }
                }
                
                return true;
            });
            
            // Sort tabs
            visibleTabs.sort((a, b) => {
                const getValue = (tab, field) => {
                    switch(field) {
                        case 'filename': return tab.getAttribute('data-filename');
                        case 'events': return parseInt(tab.getAttribute('data-events'));
                        case 'timexes': return parseInt(tab.getAttribute('data-timexes'));
                        case 'tlinks': return parseInt(tab.getAttribute('data-tlinks'));
                        case 'sentences': return parseInt(tab.getAttribute('data-sentences'));
                        default: return tab.getAttribute('data-filename');
                    }
                };
                
                const [field, order] = sortBy.split('-');
                const aVal = getValue(a, field);
                const bVal = getValue(b, field);
                
                let comparison = 0;
                if (typeof aVal === 'string') {
                    comparison = aVal.localeCompare(bVal);
                } else {
                    comparison = aVal - bVal;
                }
                
                return order === 'desc' ? -comparison : comparison;
            });
            
            // Hide all tabs first
            tabs.forEach(tab => tab.style.display = 'none');
            
            // Show and reorder visible tabs
            const tabsContainer = document.getElementById('tabs');
            visibleTabs.forEach(tab => {
                tab.style.display = 'block';
                tabsContainer.appendChild(tab); // Move to end (reorder)
            });
            
            // Update match count
            document.getElementById('matchCount').textContent = 
                `Showing ${visibleTabs.length} of ${tabs.length} files`;
            
            // If current tab is hidden, show first visible tab
            const activeTab = document.querySelector('.tab.active');
            if (!activeTab || activeTab.style.display === 'none') {
                if (visibleTabs.length > 0) {
                    const firstIndex = parseInt(visibleTabs[0].getAttribute('data-index'));
                    showTab(firstIndex);
                }
            }
        }
        
        function resetFilters() {
            document.getElementById('search').value = '';
            document.getElementById('sortBy').value = 'filename';
            document.getElementById('taskFilter').value = 'all';
            document.getElementById('minEvents').value = '0';
            document.getElementById('minLinks').value = '0';
            applyFilters();
        }
        
        // Initialize match count on load
        window.addEventListener('load', () => {
            applyFilters();
        });
        
        function initGraph(index) {
            const data = allGraphData[index];
            const container = document.getElementById(`graph-${index}`);
            const width = container.clientWidth;
            const height = 500;
            const margin = 50;
            
            const svg = d3.select(`#graph-${index}`)
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Define arrow markers for each relation type
            const defs = svg.append('defs');
            
            const relationColors = {
                'BEFORE': '#e74c3c',
                'AFTER': '#9b59b6',
                'OVERLAP': '#f39c12',
                'BEFORE-OR-OVERLAP': '#16a085',
                'OVERLAP-OR-AFTER': '#d35400',
                'VAGUE': '#95a5a6'
            };
            
            // Create arrow marker for each relation type
            Object.entries(relationColors).forEach(([relation, color]) => {
                defs.append('marker')
                    .attr('id', `arrow-${relation}-${index}`)
                    .attr('viewBox', '0 0 10 10')
                    .attr('refX', 25)
                    .attr('refY', 5)
                    .attr('markerWidth', 6)
                    .attr('markerHeight', 6)
                    .attr('orient', 'auto-start-reverse')
                    .append('path')
                    .attr('d', 'M 0 0 L 10 5 L 0 10 z')
                    .attr('fill', color);
            });
            
            const g = svg.append('g');
            
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });
            
            svg.call(zoom);
            
            function boundedBox() {
                for (let node of data.nodes) {
                    node.x = Math.max(margin, Math.min(width - margin, node.x));
                    node.y = Math.max(margin, Math.min(height - margin, node.y));
                }
            }
            
            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.links).distance(120).strength(0.5))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(35))
                .force('bounds', boundedBox);
            
            const link = g.append('g')
                .selectAll('line')
                .data(data.links)
                .enter()
                .append('line')
                .attr('stroke', d => relationColors[d.relation] || '#95a5a6')
                .attr('stroke-width', 2)
                .attr('opacity', 0.6)
                .attr('marker-end', d => `url(#arrow-${d.relation}-${index})`);
            
            const node = g.append('g')
                .selectAll('g')
                .data(data.nodes)
                .enter()
                .append('g')
                .call(d3.drag()
                    .on('start', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    })
                    .on('drag', (event, d) => {
                        d.fx = Math.max(margin, Math.min(width - margin, event.x));
                        d.fy = Math.max(margin, Math.min(height - margin, event.y));
                    })
                    .on('end', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0);
                    }));
            
            node.each(function(d) {
                const g = d3.select(this);
                if (d.type === 'event') {
                    g.append('circle')
                        .attr('r', 15)
                        .attr('fill', '#3498db')
                        .attr('stroke', '#2c3e50')
                        .attr('stroke-width', 2)
                        .style('cursor', 'pointer');
                } else {
                    g.append('rect')
                        .attr('x', -15)
                        .attr('y', -15)
                        .attr('width', 30)
                        .attr('height', 30)
                        .attr('fill', '#2ecc71')
                        .attr('stroke', '#27ae60')
                        .attr('stroke-width', 2)
                        .style('cursor', 'pointer');
                }
            });
            
            // Add click handler to nodes
            node.on('click', function(event, d) {
                event.stopPropagation();
                highlightTextElement(index, d.id);
            });
            
            const nodeLabel = node.append('text')
                .attr('text-anchor', 'middle')
                .attr('dy', 25)
                .attr('font-size', '9px')
                .attr('font-weight', 'bold')
                .attr('class', 'node-label')
                .text(d => d.id);
            
            node.append('title')
                .text(d => `${d.id}: "${d.fullText}"`);
            
            simulation.on('tick', () => {
                data.nodes.forEach(d => {
                    d.x = Math.max(margin, Math.min(width - margin, d.x));
                    d.y = Math.max(margin, Math.min(height - margin, d.y));
                });
                
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node.attr('transform', d => `translate(${d.x},${d.y})`);
            });
            
            graphInstances[index] = { 
                svg, 
                zoom, 
                simulation, 
                g, 
                nodeLabel,
                node,
                showingText: false 
            };
            
            setTimeout(() => fitToView(index), 1000);
        }
        
        function resetGraph(index) {
            if (graphInstances[index]) {
                allGraphData[index].nodes.forEach(d => {
                    d.fx = null;
                    d.fy = null;
                });
                graphInstances[index].simulation.alpha(1).restart();
            }
        }
        
        function fitToView(index) {
            if (graphInstances[index]) {
                const { svg, zoom, g } = graphInstances[index];
                const bounds = g.node().getBBox();
                const width = svg.attr('width');
                const height = svg.attr('height');
                
                if (bounds.width === 0 || bounds.height === 0) return;
                
                const scale = 0.9 / Math.max(bounds.width / width, bounds.height / height);
                const translate = [
                    width / 2 - scale * (bounds.x + bounds.width / 2),
                    height / 2 - scale * (bounds.y + bounds.height / 2)
                ];
                
                svg.transition().duration(750)
                    .call(zoom.transform, d3.zoomIdentity
                        .translate(translate[0], translate[1])
                        .scale(scale));
            }
        }
        
        function zoomIn(index) {
            if (graphInstances[index]) {
                graphInstances[index].svg.transition().duration(300)
                    .call(graphInstances[index].zoom.scaleBy, 1.3);
            }
        }
        
        function zoomOut(index) {
            if (graphInstances[index]) {
                graphInstances[index].svg.transition().duration(300)
                    .call(graphInstances[index].zoom.scaleBy, 0.7);
            }
        }
        
        function toggleGraphLabels(index) {
            if (graphInstances[index]) {
                const instance = graphInstances[index];
                instance.showingText = !instance.showingText;
                const data = allGraphData[index];
                
                instance.nodeLabel.text(d => {
                    if (instance.showingText) {
                        return d.label || d.fullText.substring(0, 15);
                    } else {
                        return d.id;
                    }
                });
                
                const statusText = instance.showingText ? 'Labels: Text' : 'Labels: ID';
                document.getElementById(`label-status-${index}`).textContent = statusText;
            }
        }
        
        function highlightNode(index, nodeId) {
            if (graphInstances[index]) {
                const instance = graphInstances[index];
                
                // Remove previous highlights
                instance.node.classed('node-highlighted', false);
                
                // Highlight the selected node
                instance.node.filter(d => d.id === nodeId)
                    .classed('node-highlighted', true);
                
                // Find the node position and pan to it
                const nodeData = allGraphData[index].nodes.find(n => n.id === nodeId);
                if (nodeData) {
                    const width = instance.svg.attr('width');
                    const height = instance.svg.attr('height');
                    const scale = d3.zoomTransform(instance.svg.node()).k || 1;
                    
                    instance.svg.transition().duration(500)
                        .call(instance.zoom.transform, d3.zoomIdentity
                            .translate(width / 2 - nodeData.x * scale, height / 2 - nodeData.y * scale)
                            .scale(scale));
                    
                    // Remove highlight after 2 seconds
                    setTimeout(() => {
                        instance.node.classed('node-highlighted', false);
                    }, 2000);
                }
            }
        }
        
        function highlightTextElement(index, nodeId) {
            // Find the tab content
            const tabContent = document.querySelectorAll('.tab-content')[index];
            if (!tabContent) return;
            
            // Remove previous text highlights
            tabContent.querySelectorAll('.event, .timex').forEach(el => {
                el.style.outline = '';
                el.style.outlineOffset = '';
            });
            
            // Find and highlight the text element
            const textElement = tabContent.querySelector(`[data-id="${nodeId}"]`);
            if (textElement) {
                textElement.style.outline = '3px solid #f39c12';
                textElement.style.outlineOffset = '2px';
                
                // Scroll the text section into view
                textElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Remove highlight after 2 seconds
                setTimeout(() => {
                    textElement.style.outline = '';
                    textElement.style.outlineOffset = '';
                }, 2000);
            }
        }
        
        // Initialize first graph
        if (allGraphData[0].nodes.length > 0) {
            initGraph(0);
        }
        
        // Attach click handlers to events and timexes in text sections
        function initTextClickHandlers() {
            document.querySelectorAll('.tab-content').forEach((tabContent, index) => {
                // Find all events and timexes in this tab
                const events = tabContent.querySelectorAll('.event[data-id]');
                const timexes = tabContent.querySelectorAll('.timex[data-id]');
                
                events.forEach(eventEl => {
                    eventEl.style.cursor = 'pointer';
                    eventEl.addEventListener('click', function() {
                        const nodeId = this.getAttribute('data-id');
                        highlightNode(index, nodeId);
                    });
                });
                
                timexes.forEach(timexEl => {
                    timexEl.style.cursor = 'pointer';
                    timexEl.addEventListener('click', function() {
                        const nodeId = this.getAttribute('data-id');
                        highlightNode(index, nodeId);
                    });
                });
            });
        }
        
        // Initialize click handlers after page load
        initTextClickHandlers();
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✓ Multi-file visualization exported to: {output_path}")
    print(f"  Total files: {len(files)}")
    print(f"  Total events: {total_events}")
    print(f"  Total time expressions: {total_timexes}")
    print(f"  Total temporal links: {total_tlinks}")


def main():
    parser = argparse.ArgumentParser(
        description='Visualize multiple TempEval files in one page',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('directories', nargs='+', help='Directories containing .tml files (can specify multiple)')
    parser.add_argument('--output', '-o', default='all_files.html', help='Output HTML file (default: all_files.html)')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of files to process')
    
    args = parser.parse_args()
    
    # Find all TML files from all directories
    tml_files = []
    for directory in args.directories:
        path = Path(directory)
        if not path.exists():
            print(f"Warning: Directory not found: {directory}")
            continue
        
        dir_files = sorted(path.glob('*.tml'))
        tml_files.extend(dir_files)
        print(f"Found {len(dir_files)} files in {directory}")
    
    if not tml_files:
        print(f"Error: No .tml files found in any directory")
        sys.exit(1)
    
    if args.limit:
        tml_files = tml_files[:args.limit]
    
    print(f"\nTotal: {len(tml_files)} .tml files")
    
    generate_multi_file_html(tml_files, args.output)


if __name__ == '__main__':
    main()
