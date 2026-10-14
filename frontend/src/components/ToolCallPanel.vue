<template>
  <section class="tools-panel">
    <div class="section-head">
      <p class="eyebrow">Tools</p>
      <strong>{{ runtime.activeRun?.tools.length || 0 }}</strong>
    </div>

    <div class="tool-list">
      <article v-for="tool in runtime.activeRun?.tools || []" :key="tool.id" class="tool-row">
        <div class="tool-head">
          <div class="tool-name">
            <span :class="['tool-status', tool.status]"></span>
            <strong>{{ tool.name }}</strong>
          </div>
          <span class="status-label">
            {{ statusLabel(tool.status) }}{{ tool.durationMs !== undefined ? ` · ${tool.durationMs} ms` : '' }}
          </span>
        </div>
        <div v-if="hasResult(tool.result)" class="result-block">
          <div class="result-top">
            <span>Tool result</span>
            <a
              v-if="extractUrl(tool.result)"
              :href="extractUrl(tool.result)"
              target="_blank"
              rel="noreferrer"
            >
              Open link
            </a>
          </div>
          <dl v-if="summaryRows(tool.result).length" class="result-summary">
            <template v-for="row in summaryRows(tool.result)" :key="row.label">
              <dt>{{ row.label }}</dt>
              <dd>{{ row.value }}</dd>
            </template>
          </dl>
          <div v-if="searchSources(tool.result).length" class="source-list">
            <strong>Sources</strong>
            <ol>
              <li v-for="source in searchSources(tool.result)" :key="source.url">
                <a :href="source.url" target="_blank" rel="noreferrer">
                  {{ source.title || source.url }}
                </a>
                <span v-if="source.kind">{{ source.kind }}</span>
              </li>
            </ol>
          </div>
          <pre>{{ formatResult(tool.result) }}</pre>
        </div>
        <details>
          <summary>Arguments</summary>
          <pre>{{ formatParams(tool.params) }}</pre>
        </details>
      </article>
    </div>

    <div v-if="!runtime.activeRun?.tools.length" class="empty">No tool calls yet.</div>
  </section>
</template>

<script setup lang="ts">
import { useRuntimeStore } from '@/stores/runtime'
import type { RuntimeStatus } from '@/api/types'

const runtime = useRuntimeStore()

function statusLabel(status: RuntimeStatus) {
  const labels: Record<RuntimeStatus, string> = {
    idle: 'Waiting',
    active: 'Running',
    done: 'Complete',
    failed: 'Failed',
  }
  return labels[status]
}

function hasResult(result: unknown) {
  return result !== undefined && result !== null && result !== ''
}

function formatParams(params: unknown) {
  return JSON.stringify(params || {}, null, 2)
}

function formatResult(result: unknown) {
  const parsed = parseResult(result)
  if (typeof parsed === 'string') return parsed
  return JSON.stringify(parsed, null, 2)
}

function parseResult(result: unknown): unknown {
  if (typeof result !== 'string') return result
  const trimmed = result.trim()
  if (!trimmed) return ''
  try {
    return JSON.parse(trimmed)
  } catch {
    return result
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function extractUrl(result: unknown) {
  const parsed = parseResult(result)
  if (isRecord(parsed) && typeof parsed.url === 'string') return parsed.url
  const sources = searchSources(parsed)
  if (sources.length) return sources[0].url
  if (typeof parsed !== 'string') return ''
  return parsed.match(/https?:\/\/\S+/)?.[0] || ''
}

function summaryRows(result: unknown) {
  const parsed = parseResult(result)
  if (!isRecord(parsed)) return []
  const labels: Record<string, string> = {
    ok: 'Status',
    status: 'HTTP status',
    provider: 'Provider',
    query: 'Query',
    search_depth: 'Search depth',
    time_range: 'Time range',
    result_count: 'Results',
    title: 'Title',
    document_id: 'Document ID',
    url: 'URL',
    blocks_created: 'Blocks written',
    reply_text: 'Reply text',
    error: 'Error',
  }
  return Object.entries(labels)
    .filter(([key]) => parsed[key] !== undefined && parsed[key] !== null && parsed[key] !== '')
    .map(([key, label]) => ({
      label,
      value: key === 'ok' ? (parsed[key] ? 'Success' : 'Failed') : String(parsed[key]),
    }))
}

function searchSources(result: unknown) {
  const parsed = parseResult(result)
  if (!isRecord(parsed) || !Array.isArray(parsed.results)) return []
  return parsed.results
    .filter(isRecord)
    .filter((item) => typeof item.url === 'string')
    .map((item) => ({
      title: typeof item.title === 'string' ? item.title : '',
      url: String(item.url),
      kind: typeof item.source_kind === 'string' ? item.source_kind : '',
    }))
}
</script>

<style scoped>
.tools-panel {
  border-top: 1px solid var(--border);
  min-height: 0;
}
.section-head {
  height: 40px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.eyebrow {
  color: var(--accent);
  font: 700 10px/1 var(--mono);
}
.tool-list {
  padding: 12px;
}
.tool-row {
  border: 1px solid var(--border);
  background: #fff;
  margin-bottom: 10px;
}
.tool-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid var(--border);
}
.tool-name {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}
.tool-name strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.tool-status {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--muted);
}
.tool-status.active {
  background: var(--accent);
}
.tool-status.done {
  background: var(--green);
}
.tool-status.failed {
  background: var(--red);
}
.status-label {
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  white-space: nowrap;
}
.result-block {
  padding: 10px;
  border-bottom: 1px solid rgba(209, 213, 219, 0.6);
  background: #fbfdff;
}
.result-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.result-top span {
  color: var(--accent);
  font: 700 10px/1 var(--mono);
}
.result-top a {
  color: var(--accent);
  font-size: 12px;
  text-decoration: none;
  border-bottom: 1px solid currentColor;
}
.result-summary {
  display: grid;
  grid-template-columns: 66px minmax(0, 1fr);
  gap: 6px 10px;
  margin: 0 0 9px;
  padding: 8px;
  background: #fff;
  border: 1px solid rgba(209, 213, 219, 0.7);
}
.result-summary dt {
  color: var(--muted);
  font: 700 10px/1.4 var(--mono);
}
.result-summary dd {
  margin: 0;
  min-width: 0;
  color: #111827;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.source-list {
  margin: 0 0 9px;
  padding: 9px;
  background: #fff;
  border: 1px solid rgba(209, 213, 219, 0.7);
}
.source-list > strong {
  color: var(--muted);
  font: 700 10px/1 var(--mono);
}
.source-list ol {
  margin: 8px 0 0;
  padding-left: 20px;
}
.source-list li {
  margin: 6px 0;
  font-size: 12px;
  line-height: 1.4;
}
.source-list a {
  color: var(--accent);
  overflow-wrap: anywhere;
}
.source-list span {
  display: block;
  color: var(--muted);
  font: 600 9px/1.4 var(--mono);
}
details {
  border-top: 1px solid rgba(209, 213, 219, 0.6);
}
summary {
  padding: 8px 10px;
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  cursor: pointer;
}
pre {
  margin: 0;
  padding: 0 10px 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 500 11px/1.5 var(--mono);
}
.empty {
  padding: 14px;
  color: var(--muted);
  font-size: 13px;
}
</style>
