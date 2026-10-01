<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "风电场站", "created": 0, "pending": 0, "abnormal": 0}, {"name": "风电机组", "created": 0, "pending": 0, "abnormal": 0}, {"name": "叶片", "created": 0, "pending": 0, "abnormal": 0}, {"name": "齿轮箱", "created": 0, "pending": 0, "abnormal": 0}, {"name": "发电机", "created": 0, "pending": 0, "abnormal": 0}, {"name": "变桨系统", "created": 0, "pending": 0, "abnormal": 0}, {"name": "偏航系统", "created": 0, "pending": 0, "abnormal": 0}, {"name": "测风塔", "created": 0, "pending": 0, "abnormal": 0}, {"name": "集电线路", "created": 0, "pending": 0, "abnormal": 0}, {"name": "升压站", "created": 0, "pending": 0, "abnormal": 0}, {"name": "功率预测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "振动监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "缺陷登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "检修任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "备件领用", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡视检查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "验收确认", "created": 0, "pending": 0, "abnormal": 0}, {"name": "电量结算", "created": 0, "pending": 0, "abnormal": 0}, {"name": "社区投诉台账", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
