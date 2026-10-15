<template>
  <section class="messages-panel">
    <div class="tabs">
      <button :class="{ active: tab === 'current' }" @click="tab = 'current'">Current context</button>
      <button :class="{ active: tab === 'initial' }" @click="tab = 'initial'">Initial messages</button>
    </div>

    <div class="message-list">
      <article v-for="(message, index) in displayMessages" :key="index" class="message-row">
        <div class="message-meta">
          <span>{{ message.role }}</span>
          <span v-if="message.name">{{ message.name }}</span>
        </div>
        <div class="message-body">
          <SafeMarkdown
            v-if="isMarkdownContent(message)"
            class="message-markdown"
            :text="message.content as string"
          />
          <pre v-else-if="hasContent(message)">{{ formatContent(String(message.content)) }}</pre>
          <div
            v-for="(toolCall, toolIndex) in message.displayToolCalls"
            :key="toolIndex"
            class="tool-request"
          >
            <span>Requests tool</span>
            <pre>{{ JSON.stringify(toolCall, null, 2) }}</pre>
          </div>
        </div>
      </article>
    </div>

    <div v-if="!displayMessages.length" class="empty">No message context yet.</div>
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

type DisplayMessage = RuntimeMessage & { displayToolCalls: unknown[] }

const displayMessages = computed(() => collapseAssistantMessages(messages.value))

function isMarkdownContent(message: RuntimeMessage) {
  return message.role === 'assistant'
    && typeof message.content === 'string'
    && message.content.trim().length > 0
}

function hasContent(message: RuntimeMessage) {
  return typeof message.content === 'string' && message.content.trim().length > 0
}

function collapseAssistantMessages(source: RuntimeMessage[]): DisplayMessage[] {
  const result: DisplayMessage[] = []
  for (const message of source) {
    const content = typeof message.content === 'string' ? message.content : ''
    const calls = extractToolCalls(message)
    const previous = result[result.length - 1]
    if (message.role === 'assistant' && previous?.role === 'assistant') {
      previous.content = [String(previous.content || '').trim(), content.trim()]
        .filter(Boolean)
        .join('\n\n')
      previous.displayToolCalls.push(...calls)
      continue
    }
    if (!content.trim() && !calls.length) continue
    result.push({ ...message, content, displayToolCalls: calls })
  }
  return result
}

function extractToolCalls(message: RuntimeMessage): unknown[] {
  if (message.tool_call) return [message.tool_call]
  if (Array.isArray(message.tool_calls)) return message.tool_calls
  return message.tool_calls ? [message.tool_calls] : []
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
  background: #f9fafb;
}
.message-row {
  position: relative;
  z-index: 0;
  min-width: 0;
  overflow: clip;
  contain: layout paint;
  isolation: isolate;
  border: 1px solid var(--border);
  background: #fff;
  margin: 0;
}
.message-row + .message-row {
  border-top: 0;
}
.message-meta {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  text-transform: uppercase;
  background: #fff;
}
.message-body {
  display: flow-root;
  min-width: 0;
  overflow: clip;
  contain: layout paint;
  background: #fff;
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
.tool-request {
  border-top: 1px solid var(--border);
  background: #f8fafc;
}
.tool-request > span {
  display: block;
  padding: 8px 10px 0;
  color: var(--accent);
  font: 700 9px/1 var(--mono);
  text-transform: uppercase;
}
.tool-request pre {
  color: #334155;
}
.empty {
  padding: 16px;
  color: var(--muted);
  font-size: 13px;
}
</style>
