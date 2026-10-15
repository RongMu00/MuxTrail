<template>
  <section class="messages-panel">
    <div class="tabs">
      <button :class="{ active: tab === 'current' }" @click="tab = 'current'">Current context</button>
      <button :class="{ active: tab === 'initial' }" @click="tab = 'initial'">Initial messages</button>
    </div>

    <div class="message-list">
      <article v-for="(message, index) in messages" :key="index" class="message-row">
        <div class="message-meta">
          <span>{{ message.role }}</span>
          <span v-if="message.name">{{ message.name }}</span>
        </div>
        <div class="message-body">
          <SafeMarkdown
            v-if="isMarkdownMessage(message)"
            class="message-markdown"
            :text="message.content as string"
          />
          <pre v-else-if="formatMessage(message)">{{ formatMessage(message) }}</pre>
          <p v-else class="empty-content">No textual content.</p>
        </div>
      </article>
    </div>

    <div v-if="!messages.length" class="empty">No message context yet.</div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRuntimeStore } from '@/stores/runtime'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import type { RuntimeMessage } from '@/api/types'

const runtime = useRuntimeStore()
const tab = ref<'current' | 'initial'>('current')

const messages = computed(() => {
  const run = runtime.activeRun
  if (!run) return []
  return tab.value === 'initial' ? run.initialMessages : runtime.activeMessages
})

function formatMessage(message: RuntimeMessage) {
  if (message.tool_call) return JSON.stringify(message.tool_call, null, 2)
  if (message.tool_calls) return JSON.stringify(message.tool_calls, null, 2)
  if (typeof message.content === 'string') return formatContent(message.content)
  return JSON.stringify(message, null, 2)
}

function isMarkdownMessage(message: RuntimeMessage) {
  return message.role === 'assistant'
    && !message.tool_call
    && !message.tool_calls
    && typeof message.content === 'string'
    && message.content.trim().length > 0
}

function formatContent(content: string) {
  const trimmed = content.trim()
  if (!trimmed || !['{', '['].includes(trimmed[0])) return content
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return content
  }
}
</script>

<style scoped>
.messages-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--border);
}
.tabs button {
  height: 38px;
  border: 0;
  border-right: 1px solid var(--border);
  background: #f9fafb;
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  cursor: pointer;
}
.tabs button:last-child {
  border-right: 0;
}
.tabs button.active {
  background: #fff;
  color: var(--accent);
}
.message-list {
  padding: 12px;
  min-width: 0;
}
.message-row {
  min-width: 0;
  overflow: hidden;
  contain: layout paint;
  border: 1px solid var(--border);
  background: #fff;
  margin-bottom: 10px;
}
.message-meta {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  text-transform: uppercase;
}
.message-body {
  min-width: 0;
  max-height: 360px;
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.message-body pre {
  display: block;
  width: 100%;
  max-width: 100%;
  padding: 10px;
  margin: 0;
  color: #111827;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font: 500 11px/1.55 var(--mono);
}
.message-markdown {
  display: block;
  min-width: 0;
  max-width: 100%;
  padding: 10px;
  color: #111827;
  font: 500 11px/1.55 var(--mono);
}
.empty-content {
  margin: 0;
  padding: 10px;
  color: var(--muted);
  font: 500 11px/1.55 var(--mono);
  font-style: italic;
}
.empty {
  padding: 16px;
  color: var(--muted);
  font-size: 13px;
}
</style>
