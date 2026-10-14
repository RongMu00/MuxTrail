<template>
  <div class="safe-markdown">
    <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
      <ul v-if="block.kind === 'list'">
        <li v-for="(line, lineIndex) in block.lines" :key="lineIndex">
          <template v-for="(token, tokenIndex) in line" :key="tokenIndex">
            <a
              v-if="token.kind === 'link'"
              :href="token.href"
              target="_blank"
              rel="noreferrer"
            >{{ token.text }}</a>
            <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
            <span v-else>{{ token.text }}</span>
          </template>
        </li>
      </ul>
      <p v-else>
        <template v-for="(token, tokenIndex) in block.lines[0]" :key="tokenIndex">
          <a
            v-if="token.kind === 'link'"
            :href="token.href"
            target="_blank"
            rel="noreferrer"
          >{{ token.text }}</a>
          <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
          <span v-else>{{ token.text }}</span>
        </template>
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type InlineToken = {
  kind: 'text' | 'link' | 'code'
  text: string
  href?: string
}

type MarkdownBlock = {
  kind: 'paragraph' | 'list'
  lines: InlineToken[][]
}

const props = defineProps<{ text: string }>()

const blocks = computed(() => parseBlocks(props.text || ''))

function parseInline(value: string): InlineToken[] {
  const tokens: InlineToken[] = []
  const pattern = /`([^`\n]+)`|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g
  let cursor = 0
  for (const match of value.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) tokens.push({ kind: 'text', text: value.slice(cursor, index) })
    if (match[1] !== undefined) {
      tokens.push({ kind: 'code', text: match[1] })
    } else {
      tokens.push({ kind: 'link', text: match[2], href: match[3] })
    }
    cursor = index + match[0].length
  }
  if (cursor < value.length) tokens.push({ kind: 'text', text: value.slice(cursor) })
  if (!tokens.length) tokens.push({ kind: 'text', text: value })
  return tokens
}

function parseBlocks(raw: string): MarkdownBlock[] {
  const lines = raw.replace(/\\n/g, '\n').split('\n')
  const result: MarkdownBlock[] = []
  let paragraph: string[] = []
  let list: InlineToken[][] = []

  const flushParagraph = () => {
    if (!paragraph.length) return
    result.push({ kind: 'paragraph', lines: [parseInline(paragraph.join('\n'))] })
    paragraph = []
  }
  const flushList = () => {
    if (!list.length) return
    result.push({ kind: 'list', lines: list })
    list = []
  }

  for (const line of lines) {
    const listMatch = line.match(/^\s*[-*]\s+(.+)$/)
    if (listMatch) {
      flushParagraph()
      list.push(parseInline(listMatch[1]))
      continue
    }
    flushList()
    if (!line.trim()) {
      flushParagraph()
      continue
    }
    paragraph.push(line)
  }
  flushList()
  flushParagraph()
  return result
}
</script>

<style scoped>
.safe-markdown {
  color: inherit;
  overflow-wrap: anywhere;
}
p {
  margin: 0 0 0.75em;
  white-space: pre-wrap;
}
p:last-child,
ul:last-child {
  margin-bottom: 0;
}
ul {
  margin: 0 0 0.75em;
  padding-left: 1.4em;
}
li + li {
  margin-top: 0.35em;
}
a {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
code {
  border: 1px solid var(--border);
  background: #f3f4f6;
  padding: 0.08em 0.3em;
  font: 500 0.92em/1.4 var(--mono);
}
</style>
