<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>社区噪音光影投诉台账</h2>
        <p class="page-desc">按投诉来源登记噪音、光影投诉的受理时间、影响时段、核查结论与答复期限；超过答复期限未答复的记录自动进入督办清单。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记社区投诉</button>
        <button class="btn" type="button" @click="exportRows">导出投诉台账清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <section v-if="supervisionRows.length" class="supervision-panel">
      <h3>超期未答复督办清单（{{ supervisionRows.length }} 条，时限按最早受理时间计算）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>投诉编号</th>
            <th>投诉来源</th>
            <th>投诉类型</th>
            <th>最早受理时间</th>
            <th>答复期限</th>
            <th>超期天数</th>
            <th>重复次数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in supervisionRows" :key="`supervision-${row.id}`">
            <td>{{ row.投诉编号 }}</td>
            <td>{{ row.投诉来源 }}</td>
            <td>{{ row.投诉类型 }}</td>
            <td>{{ row.受理时间 }}</td>
            <td>{{ row.答复期限 }}</td>
            <td>{{ row.超期天数 }} 天</td>
            <td>{{ row.重复次数 }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openReply(row)">
                {{ draftIds.has(row.id) ? '继续答复' : '去答复' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="filters.keyword" placeholder="按投诉编号、投诉来源或类型检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key">{{ column.label }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column.key">{{ cell(row, column.key) }}</td>
          <td class="row-actions">
            <button v-if="row.status !== '已答复'" class="link" type="button" @click="openReply(row)">
              {{ draftIds.has(row.id) ? '继续答复' : '答复' }}
            </button>
            <button class="link" type="button" @click="openDetail(row)">明细</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条投诉记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="dialog-mask" @click.self="createVisible = false">
      <div class="dialog">
        <h3>登记社区投诉</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>投诉来源 *</span>
            <select v-model="createForm.投诉来源">
              <option value="" disabled>请选择投诉来源</option>
              <option v-for="source in sources" :key="source" :value="source">{{ source }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>投诉类型 *</span>
            <select v-model="createForm.投诉类型">
              <option v-for="kind in kinds" :key="kind" :value="kind">{{ kind }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>受理时间 *</span>
            <input v-model="createForm.受理时间" type="datetime-local" />
          </label>
          <label class="form-item">
            <span>影响时段 *</span>
            <input v-model="createForm.影响时段" placeholder="如：夜间 22:00-次日06:00" />
          </label>
          <label class="form-item">
            <span>答复期限</span>
            <input v-model="createForm.答复期限" type="date" />
            <em class="hint-text">留空则按受理时间 +5 天自动计算</em>
          </label>
          <label class="form-item">
            <span>备注</span>
            <textarea v-model="createForm.备注" placeholder="补充说明投诉具体情况"></textarea>
          </label>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="dialog-foot">
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="createSubmitting" @click="submitCreate">
            {{ createSubmitting ? '提交中…' : '提交登记' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="replyVisible && replyTarget" class="dialog-mask" @click.self="closeReply">
      <div class="dialog">
        <h3>答复投诉 {{ replyTarget.投诉编号 }}</h3>
        <p class="hint-text">
          {{ replyTarget.投诉来源 }} · {{ replyTarget.投诉类型 }} · 最早受理 {{ replyTarget.受理时间 }} · 答复期限 {{ replyTarget.答复期限 }}
          <template v-if="replyTarget.重复次数">· 已合并 {{ replyTarget.重复次数 }} 条重复投诉</template>
        </p>
        <div class="form-grid">
          <label class="form-item">
            <span>核查结论 *</span>
            <textarea v-model="replyForm.核查结论" placeholder="填写现场核查得出的结论"></textarea>
          </label>
          <label class="form-item">
            <span>答复内容 *</span>
            <textarea v-model="replyForm.答复内容" placeholder="填写给投诉人的答复内容"></textarea>
          </label>
        </div>
        <p v-if="replyHint" class="hint-text">{{ replyHint }}</p>
        <p v-if="replyError" class="error-text">{{ replyError }}</p>
        <div class="dialog-foot">
          <button class="btn ghost" type="button" @click="closeReply">暂不提交</button>
          <button class="btn primary" type="button" :disabled="replySubmitting" @click="submitReply">
            {{ replySubmitting ? '提交中…' : (replyError ? '重试提交答复' : '提交答复') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="detailVisible && detailRow" class="dialog-mask" @click.self="detailVisible = false">
      <div class="dialog">
        <h3>投诉明细 {{ detailRow.投诉编号 }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field.key">
            <dt>{{ field.label }}</dt>
            <dd>{{ cell(detailRow, field.key) }}</dd>
          </template>
        </dl>
        <template v-if="detailDuplicates.length">
          <h4 class="sub-title">重复投诉记录（{{ detailRow.重复次数 }} 条，督办时限按最早受理时间计算）</h4>
          <table class="data-table">
            <thead>
              <tr><th>受理时间</th><th>投诉来源</th><th>备注</th></tr>
            </thead>
            <tbody>
              <tr v-for="(dup, index) in detailDuplicates" :key="index">
                <td>{{ dup.受理时间 }}</td>
                <td>{{ dup.投诉来源 }}</td>
                <td>{{ dup.备注 || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div class="dialog-foot">
          <button class="btn" type="button" @click="detailVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchJson, request } from '@/api/client'

interface DuplicateEntry {
  受理时间: string
  投诉来源: string
  投诉类型: string
  影响时段: string
  备注: string
}

interface ComplaintRow {
  id: number
  status: string
  投诉编号: string
  投诉来源: string
  投诉类型: string
  受理时间: string
  影响时段: string
  核查结论: string
  答复内容: string
  答复时间: string
  答复期限: string
  备注: string
  重复次数: number
  重复记录: DuplicateEntry[]
  超期天数?: number
}

const ENDPOINT = '/api/complaint'
const DRAFT_PREFIX = 'complaint:reply-draft:'
const columns = [
  { key: '投诉编号', label: '投诉编号' },
  { key: '投诉来源', label: '投诉来源' },
  { key: '投诉类型', label: '投诉类型' },
  { key: '受理时间', label: '受理时间' },
  { key: '影响时段', label: '影响时段' },
  { key: '核查结论', label: '核查结论' },
  { key: '答复期限', label: '答复期限' },
  { key: 'status', label: '状态' },
  { key: '重复次数', label: '重复' },
]
const detailFields = [
  { key: '投诉编号', label: '投诉编号' },
  { key: '投诉来源', label: '投诉来源' },
  { key: '投诉类型', label: '投诉类型' },
  { key: '受理时间', label: '最早受理时间' },
  { key: '影响时段', label: '影响时段' },
  { key: '答复期限', label: '答复期限' },
  { key: '核查结论', label: '核查结论' },
  { key: '答复内容', label: '答复内容' },
  { key: '答复时间', label: '答复时间' },
  { key: 'status', label: '状态' },
  { key: '备注', label: '备注' },
]
const statuses = ['待答复', '已答复']
const sources = ['12345热线', '社区网格员', '业主直接来电', '微信公众号', '其他']
const kinds = ['噪音投诉', '光影投诉']

const rows = ref<ComplaintRow[]>([])
const supervisionRows = ref<ComplaintRow[]>([])
const stats = ref([
  { label: '待答复投诉', value: 0 },
  { label: '超期督办', value: 0 },
  { label: '重复合并', value: 0 },
  { label: '已答复', value: 0 },
])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref({ keyword: '', status: '' })
const appliedFilters = ref({ keyword: '', status: '' })
const draftIds = ref<Set<number>>(new Set())

const emptyHint = computed(() => {
  if (appliedFilters.value.keyword) {
    return `未检索到与「${appliedFilters.value.keyword}」匹配的投诉记录，可调整关键词重新查询或登记新投诉`
  }
  if (appliedFilters.value.status) {
    return `当前没有「${appliedFilters.value.status}」状态的投诉记录，可切换状态或重置条件`
  }
  return '暂无社区投诉记录，可点击右上角登记噪音或光影投诉'
})

function cell(row: ComplaintRow, key: string): string {
  const value = row[key as keyof ComplaintRow]
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return String(value.length)
  return String(value)
}

function scanDrafts() {
  const found = new Set<number>()
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index)
    if (key && key.startsWith(DRAFT_PREFIX)) {
      const id = Number(key.slice(DRAFT_PREFIX.length))
      if (Number.isFinite(id)) found.add(id)
    }
  }
  draftIds.value = found
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) query.set('keyword', filters.value.keyword.trim())
  if (filters.value.status) query.set('status', filters.value.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('投诉台账列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    appliedFilters.value = { ...filters.value }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉台账列表读取失败'
  }
}

async function reloadSupervision() {
  try {
    const payload = await fetchJson<{ items: ComplaintRow[] }>(`${ENDPOINT}/supervision`)
    supervisionRows.value = payload.items ?? []
  } catch {
    supervisionRows.value = []
  }
}

async function reloadSummary() {
  try {
    const payload = await fetchJson<Record<string, number>>(`${ENDPOINT}/summary`)
    stats.value = [
      { label: '待答复投诉', value: payload['待答复'] ?? 0 },
      { label: '超期督办', value: payload['督办中'] ?? 0 },
      { label: '重复合并', value: payload['重复合并'] ?? 0 },
      { label: '已答复', value: payload['已答复'] ?? 0 },
    ]
  } catch {
    // 概览读取失败时保留旧数据，列表错误已在 reload 里统一提示
  }
}

async function refreshAll() {
  await Promise.all([reload(), reloadSupervision(), reloadSummary()])
}

const createVisible = ref(false)
const createSubmitting = ref(false)
const createError = ref('')
const emptyCreateForm = () => ({
  投诉来源: '',
  投诉类型: '噪音投诉',
  受理时间: '',
  影响时段: '',
  答复期限: '',
  备注: '',
})
const createForm = ref(emptyCreateForm())

function openCreate() {
  createError.value = ''
  noticeMessage.value = ''
  createForm.value = emptyCreateForm()
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  createForm.value.受理时间 = now.toISOString().slice(0, 16)
  createVisible.value = true
}

async function submitCreate() {
  const missing: string[] = []
  if (!createForm.value.投诉来源.trim()) missing.push('投诉来源')
  if (!createForm.value.受理时间.trim()) missing.push('受理时间')
  if (!createForm.value.影响时段.trim()) missing.push('影响时段')
  if (missing.length) {
    createError.value = `缺少必填字段：${missing.join('、')}。投诉来源与影响时段是登记和查重的依据，补齐后才能提交`
    return
  }
  createSubmitting.value = true
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '投诉登记失败，请检查填写内容')
    }
    createVisible.value = false
    await refreshAll()
    noticeMessage.value = payload.message ?? '社区投诉已登记'
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '投诉登记失败，请稍后重试'
  } finally {
    createSubmitting.value = false
  }
}

const replyVisible = ref(false)
const replySubmitting = ref(false)
const replyError = ref('')
const replyHint = ref('')
const replyTarget = ref<ComplaintRow | null>(null)
const replyForm = ref({ 核查结论: '', 答复内容: '' })

watch(replyForm, (value) => {
  if (replyVisible.value && replyTarget.value) {
    localStorage.setItem(`${DRAFT_PREFIX}${replyTarget.value.id}`, JSON.stringify(value))
    scanDrafts()
  }
}, { deep: true })

function openReply(row: ComplaintRow) {
  replyTarget.value = row
  replyError.value = ''
  noticeMessage.value = ''
  const saved = localStorage.getItem(`${DRAFT_PREFIX}${row.id}`)
  if (saved) {
    try {
      const draft = JSON.parse(saved) as { 核查结论?: string; 答复内容?: string }
      replyForm.value = { 核查结论: draft.核查结论 ?? '', 答复内容: draft.答复内容 ?? '' }
      replyHint.value = '已恢复上次未提交的答复草稿，可接着处理这条投诉'
    } catch {
      replyForm.value = { 核查结论: '', 答复内容: '' }
      replyHint.value = ''
    }
  } else {
    replyForm.value = { 核查结论: row.核查结论 ?? '', 答复内容: row.答复内容 ?? '' }
    replyHint.value = ''
  }
  replyVisible.value = true
}

function closeReply() {
  replyVisible.value = false
  scanDrafts()
}

async function submitReply() {
  const target = replyTarget.value
  if (!target || replySubmitting.value) return
  replySubmitting.value = true
  replyError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${target.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '提交答复', ...replyForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '答复提交失败')
    }
    localStorage.removeItem(`${DRAFT_PREFIX}${target.id}`)
    replyVisible.value = false
    replyTarget.value = null
    await refreshAll()
    scanDrafts()
    noticeMessage.value = payload.message ?? '投诉已答复'
  } catch (error) {
    // 提交失败：已填内容保留在弹窗与本地缓存中，可直接重试
    replyError.value = `${error instanceof Error ? error.message : '答复提交失败'}；已填内容已保留，可直接重试`
  } finally {
    replySubmitting.value = false
  }
}

const detailVisible = ref(false)
const detailRow = ref<ComplaintRow | null>(null)
const detailDuplicates = computed<DuplicateEntry[]>(() => detailRow.value?.重复记录 ?? [])

async function openDetail(row: ComplaintRow) {
  try {
    detailRow.value = await fetchJson<ComplaintRow>(`${ENDPOINT}/${row.id}`)
    detailVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉明细读取失败'
  }
}

onMounted(async () => {
  scanDrafts()
  await refreshAll()
})
</script>
