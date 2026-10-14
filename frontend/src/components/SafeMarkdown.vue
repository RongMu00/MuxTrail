<template>
  <div class="safe-markdown">
    <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
      <component
        :is="`h${block.level || 3}`"
        v-if="block.kind === 'heading'"
        class="markdown-heading"
      >
        <template v-for="(token, tokenIndex) in block.lines[0]" :key="tokenIndex">
          <a
            v-if="token.kind === 'link'"
            :href="token.href"
            target="_blank"
            rel="noreferrer"
          >{{ token.text }}</a>
          <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
          <strong v-else-if="token.kind === 'strong'">{{ token.text }}</strong>
          <span v-else>{{ token.text }}</span>
        </template>
      </component>
      <ul v-else-if="block.kind === 'list'">
        <li v-for="(line, lineIndex) in block.lines" :key="lineIndex">
          <template v-for="(token, tokenIndex) in line" :key="tokenIndex">
            <a
              v-if="token.kind === 'link'"
              :href="token.href"
              target="_blank"
              rel="noreferrer"
            >{{ token.text }}</a>
            <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
            <strong v-else-if="token.kind === 'strong'">{{ token.text }}</strong>
            <span v-else>{{ token.text }}</span>
          </template>
        </li>
      </ul>
      <ol v-else-if="block.kind === 'ordered-list'">
        <li v-for="(line, lineIndex) in block.lines" :key="lineIndex">
          <template v-for="(token, tokenIndex) in line" :key="tokenIndex">
            <a
              v-if="token.kind === 'link'"
              :href="token.href"
              target="_blank"
              rel="noreferrer"
            >{{ token.text }}</a>
            <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
            <strong v-else-if="token.kind === 'strong'">{{ token.text }}</strong>
            <span v-else>{{ token.text }}</span>
          </template>
        </li>
      </ol>
      <p v-else>
        <template v-for="(token, tokenIndex) in block.lines[0]" :key="tokenIndex">
          <a
            v-if="token.kind === 'link'"
            :href="token.href"
            target="_blank"
            rel="noreferrer"
          >{{ token.text }}</a>
          <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
          <strong v-else-if="token.kind === 'strong'">{{ token.text }}</strong>
          <span v-else>{{ token.text }}</span>
        </template>
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type InlineToken = {
  kind: 'text' | 'link' | 'code' | 'strong'
  text: string
  href?: string
}

type MarkdownBlock = {
  kind: 'paragraph' | 'list' | 'ordered-list' | 'heading'
  lines: InlineToken[][]
  level?: number
}

const props = defineProps<{ text: string }>()

const blocks = computed(() => parseBlocks(props.text || ''))

function parseInline(value: string): InlineToken[] {
  const tokens: InlineToken[] = []
  const pattern = /`([^`\n]+)`|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*\n]+)\*\*|__([^_\n]+)__/g
  let cursor = 0
  for (const match of value.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) tokens.push({ kind: 'text', text: value.slice(cursor, index) })
    if (match[1] !== undefined) {
      tokens.push({ kind: 'code', text: match[1] })
    } else if (match[2] !== undefined) {
      tokens.push({ kind: 'link', text: match[2], href: match[3] })
    } else {
      tokens.push({ kind: 'strong', text: match[4] ?? match[5] })
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
  let listKind: 'list' | 'ordered-list' = 'list'

  const flushParagraph = () => {
    if (!paragraph.length) return
    result.push({ kind: 'paragraph', lines: [parseInline(paragraph.join('\n'))] })
    paragraph = []
  }
  const flushList = () => {
    if (!list.length) return
    result.push({ kind: listKind, lines: list })
    list = []
  }

  for (const line of lines) {
    const headingMatch = line.match(/^\s*(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      result.push({
        kind: 'heading',
        level: headingMatch[1].length,
        lines: [parseInline(headingMatch[2])],
      })
      continue
    }
    const listMatch = line.match(/^\s*[-*]\s+(.+)$/)
    if (listMatch) {
      flushParagraph()
      if (list.length && listKind !== 'list') flushList()
      listKind = 'list'
      list.push(parseInline(listMatch[1]))
      continue
    }
    const orderedListMatch = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (orderedListMatch) {
      flushParagraph()
      if (list.length && listKind !== 'ordered-list') flushList()
      listKind = 'ordered-list'
      list.push(parseInline(orderedListMatch[1]))
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
ul:last-child,
ol:last-child {
  margin-bottom: 0;
}
ul,
ol {
  margin: 0 0 0.75em;
  padding-left: 1.4em;
}
.markdown-heading {
  margin: 1em 0 0.45em;
  color: inherit;
  font-size: 1.08em;
  line-height: 1.35;
}
.markdown-heading:first-child {
  margin-top: 0;
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
