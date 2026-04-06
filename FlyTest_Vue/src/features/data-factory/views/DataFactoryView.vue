<template>
  <div class="data-factory-page">
    <section class="hero panel">
      <div>
        <div class="hero__eyebrow">Knowledge / Data Factory</div>
        <h1 class="hero__title">数据工厂</h1>
        <p class="hero__desc">参考 testhub_platform 的数据工厂交互，保留 7 大类工具总览、场景筛选、工具执行、记录和标签管理能力。</p>
        <div class="hero__meta">
          <span>{{ projectName }}</span>
          <span>{{ catalog.tools.length }} 个工具</span>
          <span>{{ tags.length }} 个标签</span>
          <span>{{ statistics.total_records }} 条记录</span>
        </div>
      </div>
      <div class="hero__actions">
        <a-radio-group v-model="viewMode" type="button" size="small">
          <a-radio value="category">分类导航</a-radio>
          <a-radio value="scenario">场景导航</a-radio>
        </a-radio-group>
        <a-space wrap>
          <a-button :disabled="!projectReady" @click="openReferenceBrowser('api')"><template #icon><icon-copy /></template>API 引用</a-button>
          <a-button :disabled="!projectReady" @click="openReferenceBrowser('ui')"><template #icon><icon-copy /></template>UI 引用</a-button>
          <a-button :disabled="!projectReady" @click="historyVisible = true"><template #icon><icon-history /></template>使用记录</a-button>
          <a-button :disabled="!projectReady" @click="tagManagerVisible = true"><template #icon><icon-tags /></template>标签管理</a-button>
          <a-button @click="refreshAll"><template #icon><icon-refresh /></template>刷新</a-button>
        </a-space>
      </div>
    </section>

    <section v-if="!projectReady" class="panel banner">
      <strong>当前未选择项目</strong>
      <span>{{ projectLockMessage }}</span>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <div class="section-title">{{ viewMode === 'category' ? '分类卡片总览' : '场景总览' }}</div>
          <div class="section-desc">{{ viewMode === 'category' ? '点击分类卡片会立即切换下方工具工作台。' : '点击场景卡片会立即过滤下方工具模块。' }}</div>
        </div>
        <a-input-search v-model="toolKeyword" class="tool-search" allow-clear placeholder="搜索工具名称、标识或说明" />
      </div>

      <div v-if="viewMode === 'category'" class="overview-grid">
        <button
          v-for="category in categoryCards"
          :key="category.category"
          type="button"
          class="overview-card"
          :class="{ active: focusedCategory === category.category }"
          @click="focusCategorySection(category.category)"
        >
          <div class="overview-card__top">
            <div class="overview-card__icon"><component :is="categoryIcon(category.category)" /></div>
            <div class="overview-card__count">{{ category.toolCount }}</div>
          </div>
          <div class="overview-card__title">{{ category.name }}</div>
          <div class="overview-card__desc">{{ category.description }}</div>
          <div class="overview-card__chips">
            <span v-for="name in category.scenarioNames.slice(0, 2)" :key="name">{{ name }}</span>
          </div>
          <div class="overview-card__chips">
            <span v-for="tool in category.previewTools" :key="tool.name">{{ tool.display_name }}</span>
            <span v-if="category.toolCount > category.previewTools.length" class="is-primary">+{{ category.toolCount - category.previewTools.length }}</span>
          </div>
        </button>
      </div>

      <div v-else class="scenario-grid">
        <button
          v-for="scenario in catalog.scenarios"
          :key="scenario.scenario"
          type="button"
          class="scenario-card"
          :class="{ active: selectedScenario === scenario.scenario }"
          @click="applyScenarioFilter(scenario.scenario)"
        >
          <div class="scenario-card__icon"><component :is="scenarioIcon(scenario.scenario)" /></div>
          <div class="scenario-card__title">{{ scenario.name }}</div>
          <div class="scenario-card__desc">{{ scenario.description }}</div>
          <div class="scenario-card__footer">
            <span>{{ scenario.tool_count }} 个工具</span>
            <icon-arrow-right />
          </div>
        </button>
      </div>
    </section>

    <section id="data-factory-tools" ref="toolWorkspaceSection" class="panel workspace-panel">
      <div class="section-head workspace-head">
        <div>
          <div class="section-title">{{ workspaceTitle }}</div>
          <div class="section-desc">{{ workspaceDescription }}</div>
        </div>
        <div class="workspace-actions">
          <button type="button" class="pill" :class="{ active: focusedCategory === 'all' }" @click="clearCategoryFocus">全部分类</button>
          <span class="pill active">{{ workspaceToolTotal }} 个工具</span>
        </div>
      </div>

      <div class="workspace-summary">
        <span class="pill active">场景：{{ activeScenarioLabel }}</span>
        <span class="pill">{{ toolKeyword ? `关键词：${toolKeyword}` : '未设置关键词过滤' }}</span>
      </div>

      <div class="category-list">
        <article
          v-for="category in workspaceCategories"
          :key="category.category"
          class="panel category-panel"
          :class="{ active: focusedCategory === category.category }"
        >
          <div class="category-panel__head">
            <div class="category-panel__title">
              <div class="category-panel__icon"><component :is="categoryIcon(category.category)" /></div>
              <div>
                <div class="section-title">{{ category.name }}</div>
                <div class="section-desc">{{ category.description }}</div>
              </div>
            </div>
            <span class="pill active">{{ category.visibleTools.length }} 个工具</span>
          </div>

          <div class="tool-grid">
            <button v-for="tool in category.visibleTools" :key="tool.name" type="button" class="tool-card" @click="openToolDialog(tool)">
              <div class="tool-card__icon"><component :is="categoryIcon(tool.category)" /></div>
              <div class="tool-card__body">
                <div class="tool-card__title">{{ tool.display_name }}</div>
                <div class="tool-card__desc">{{ tool.description }}</div>
                <div class="tool-card__footer">
                  <span class="pill">{{ scenarioLabel(tool.scenario) }}</span>
                  <icon-arrow-right />
                </div>
              </div>
            </button>
          </div>
        </article>

        <section v-if="!workspaceCategories.length" class="panel">
          <div class="empty">当前筛选条件下暂无可显示的工具</div>
        </section>
      </div>
    </section>

    <section class="stats-grid">
      <div class="stat-card panel"><span>总使用记录</span><strong>{{ statistics.total_records }}</strong></div>
      <div class="stat-card panel"><span>已保存记录</span><strong>{{ statistics.saved_records }}</strong></div>
      <div class="stat-card panel"><span>标签数量</span><strong>{{ tags.length }}</strong></div>
      <div class="stat-card panel"><span>可用工具</span><strong>{{ catalog.tools.length }}</strong></div>
    </section>

    <section class="panel">
      <div class="section-title">场景筛选</div>
      <div class="section-desc">点击场景后会立即过滤下方分类模块与工具卡片。</div>
      <div class="pill-row">
        <button type="button" class="pill" :class="{ active: selectedScenario === 'all' }" @click="applyScenarioFilter('all')">全部场景</button>
        <button
          v-for="scenario in catalog.scenarios"
          :key="scenario.scenario"
          type="button"
          class="pill"
          :class="{ active: selectedScenario === scenario.scenario }"
          @click="applyScenarioFilter(scenario.scenario)"
        >
          {{ scenario.name }} · {{ scenario.tool_count }}
        </button>
      </div>
    </section>

    <section class="insight-grid">
      <div class="panel" :class="{ locked: !projectReady }">
        <div class="section-title">分类使用统计</div>
        <div v-if="projectReady" class="metric-list">
          <div v-for="item in categoryBreakdown" :key="item.key" class="metric">
            <div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div>
            <div class="metric__track"><span class="metric__bar" :style="{ width: `${item.percent}%` }"></span></div>
          </div>
        </div>
        <div v-else class="empty">{{ projectLockMessage }}</div>
      </div>

      <div class="panel" :class="{ locked: !projectReady }">
        <div class="section-title">场景使用统计</div>
        <div v-if="projectReady" class="metric-list">
          <div v-for="item in scenarioBreakdown" :key="item.key" class="metric">
            <div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div>
            <div class="metric__track"><span class="metric__bar metric__bar--soft" :style="{ width: `${item.percent}%` }"></span></div>
          </div>
        </div>
        <div v-else class="empty">{{ projectLockMessage }}</div>
      </div>

      <div class="panel" :class="{ locked: !projectReady }">
        <div class="section-title">最近使用</div>
        <div v-if="projectReady && recentRecords.length" class="recent-list">
          <button v-for="record in recentRecords" :key="record.id" type="button" class="recent" @click="showRecordResult(record)">
            <div class="recent__title">{{ record.tool_display_name }}</div>
            <div class="recent__meta">{{ formatDate(record.created_at) }}</div>
            <div class="recent__preview">{{ record.preview }}</div>
          </button>
        </div>
        <div v-else class="empty">{{ projectReady ? '暂无最近使用记录' : projectLockMessage }}</div>
      </div>
    </section>

    <section class="reference-grid">
      <div class="panel" :class="{ locked: !projectReady }">
        <div class="section-head">
          <div>
            <div class="section-title">标签引用中心</div>
            <div class="section-desc">直接复制标签引用到 API 自动化请求、断言和 UI 自动化步骤中。</div>
          </div>
          <a-space wrap>
            <a-button size="small" :disabled="!projectReady" @click="openReferenceBrowser('api')">浏览 API 引用</a-button>
            <a-button size="small" :disabled="!projectReady" @click="openReferenceBrowser('ui')">浏览 UI 引用</a-button>
          </a-space>
        </div>

        <div v-if="projectReady && topReferenceTags.length" class="reference-list">
          <article v-for="tag in topReferenceTags" :key="tag.id" class="reference-item">
            <div class="reference-item__head">
              <a-tag :color="tag.color || 'arcoblue'">{{ tag.code }}</a-tag>
              <span>{{ tag.total }} 次引用</span>
            </div>
            <div class="reference-item__title">{{ tag.name }}</div>
            <div class="reference-item__preview">{{ tag.preview || '暂无标签预览' }}</div>
            <div class="reference-item__actions">
              <a-button size="mini" @click="copyTagReference(tag.code, 'api')">复制 API</a-button>
              <a-button size="mini" @click="copyTagReference(tag.code, 'ui')">复制 UI</a-button>
            </div>
          </article>
        </div>
        <div v-else class="empty">{{ projectReady ? '当前项目下暂无可引用标签' : projectLockMessage }}</div>
      </div>

      <div class="panel" :class="{ locked: !projectReady }">
        <div class="section-head">
          <div>
            <div class="section-title">记录引用中心</div>
            <div class="section-desc">已保存记录可直接复制引用，也可以点开查看具体执行结果。</div>
          </div>
          <span class="pill active">{{ referenceRecords.length }} 条可引用记录</span>
        </div>

        <div v-if="projectReady && referenceRecords.length" class="reference-list">
          <button
            v-for="record in referenceRecords"
            :key="record.id"
            type="button"
            class="reference-item reference-item--interactive"
            @click="showRecordResult(record)"
          >
            <div class="reference-item__head">
              <span class="reference-item__title">{{ record.tool_display_name }}</span>
              <span>{{ formatDate(record.created_at) }}</span>
            </div>
            <div class="reference-item__preview">{{ record.preview }}</div>
            <div class="reference-item__actions">
              <a-button size="mini" @click.stop="copyText(record.reference_placeholder_api, '已复制 API 记录引用')">复制 API</a-button>
              <a-button size="mini" @click.stop="copyText(record.reference_placeholder_ui, '已复制 UI 记录引用')">复制 UI</a-button>
            </div>
          </button>
        </div>
        <div v-else class="empty">{{ projectReady ? '当前项目下暂无已保存记录可引用' : projectLockMessage }}</div>
      </div>
    </section>

    <a-modal :visible="toolDialogVisible" :title="currentTool?.display_name || '工具执行'" width="1160px" :footer="false" @cancel="toolDialogVisible = false">
      <div v-if="currentTool" class="tool-modal">
        <div class="tool-modal__banner">
          <div>
            <div class="tool-modal__desc">{{ currentTool.description }}</div>
            <div class="hero__meta">
              <span>{{ categoryName(currentTool.category) }}</span>
              <span>{{ scenarioLabel(currentTool.scenario) }}</span>
              <span>{{ currentTool.fields.length }} 个输入项</span>
            </div>
          </div>
          <div v-if="!projectReady" class="tool-modal__lock">{{ projectLockMessage }}</div>
        </div>

        <div class="tool-modal__body">
          <section class="panel tool-pane">
            <div class="section-title">工具参数</div>
            <div v-if="toolHelperPresets.length" class="tool-helper">
              <div class="tool-helper__intro">
                <div>
                  <div class="section-title section-title--mini">Input Assistant</div>
                  <div class="section-desc">{{ toolHelperDescription }}</div>
                </div>
                <span class="pill active">{{ toolHelperPresets.length }} shortcuts</span>
              </div>
              <!-- legacy helper head hidden -->
              <!--
              <div class="tool-helper__head tool-helper__head--legacy">
                <div>
                  <div class="section-title section-title--mini">杈撳叆鍔╂墜</div>
                  <div class="section-desc">{{ toolHelperDescription }}</div>
                </div>
                <span class="pill active">{{ toolHelperPresets.length }} 涓揩鎹锋搷浣?span>
                </span>
              </div>
              -->
              <div class="tool-helper__actions">
                <a-button v-for="preset in toolHelperPresets" :key="preset.key" size="small" @click="applyToolPreset(preset)">{{ preset.label }}</a-button>
              </div>
              <div v-if="imageAssistantTip" class="field-help">{{ imageAssistantTip }}</div>
            </div>

            <div v-if="toolWorkbenchCards.length" class="tool-workbench">
              <article v-for="card in toolWorkbenchCards" :key="card.key" class="tool-workbench__card" :class="`is-${card.tone || 'default'}`">
                <span class="tool-workbench__label">{{ card.label }}</span>
                <strong class="tool-workbench__value">{{ card.value }}</strong>
                <span class="tool-workbench__help">{{ card.help }}</span>
              </article>
            </div>

            <div v-if="cronExpressionPreview" class="tool-special-panel">
              <div class="tool-special-panel__head">
                <div>
                  <div class="section-title section-title--mini">Cron Preview</div>
                  <div class="section-desc">{{ cronPreviewStatus.help }}</div>
                </div>
                <a-button size="small" @click="copyText(cronExpressionPreview, 'Cron expression copied')">Copy</a-button>
              </div>
              <pre class="tool-special-panel__code">{{ cronExpressionPreview }}</pre>
              <div class="tool-special-panel__meta">
                <span class="pill" :class="{ active: cronPreviewStatus.tone === 'success' }">{{ cronPreviewStatus.text }}</span>
                <span class="pill">{{ currentTool?.name === 'cron_generate' ? 'Generated from fields' : 'Expression mode' }}</span>
              </div>
            </div>

            <div v-if="specializedLayoutKind === 'jsonpath'" class="special-form special-form--two-columns">
              <section class="special-form__panel special-form__panel--wide">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('text', 'JSON Content') }}</label>
                  <div v-if="fieldActionItemsByName('text').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('text')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.text" :placeholder="fieldPlaceholder('text', 'Paste JSON content here')" :auto-size="{ minRows: 14, maxRows: 22 }" />
                <div class="special-form__meta-row">
                  <span class="pill" :class="{ active: currentJsonAnalysis?.status === 'valid' }">{{ currentJsonAnalysis?.summary || 'Empty' }}</span>
                  <span class="field-help">{{ currentJsonAnalysis?.help }}</span>
                </div>
              </section>

              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('path', 'JSONPath') }}</label>
                  <div v-if="fieldActionItemsByName('path').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('path')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-input v-model="toolForm.path" :placeholder="fieldPlaceholder('path', '$.items[*].id')" />
                <div class="special-form__note">
                  <strong>Common selectors</strong>
                  <code v-for="example in jsonPathSyntaxExamples" :key="example">{{ example }}</code>
                </div>
              </section>
            </div>

            <div v-else-if="specializedLayoutKind === 'json-diff'" class="special-form special-form--compare">
              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('left_text', 'JSON A') }}</label>
                  <div v-if="fieldActionItemsByName('left_text').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('left_text')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.left_text" :placeholder="fieldPlaceholder('left_text', 'Left JSON input')" :auto-size="{ minRows: 14, maxRows: 22 }" />
                <div class="special-form__meta-row">
                  <span class="pill" :class="{ active: jsonDiffLeftAnalysis?.status === 'valid' }">{{ jsonDiffLeftAnalysis?.summary || 'Empty' }}</span>
                  <span class="field-help">{{ jsonDiffLeftAnalysis?.help }}</span>
                </div>
              </section>

              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('right_text', 'JSON B') }}</label>
                  <div v-if="fieldActionItemsByName('right_text').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('right_text')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.right_text" :placeholder="fieldPlaceholder('right_text', 'Right JSON input')" :auto-size="{ minRows: 14, maxRows: 22 }" />
                <div class="special-form__meta-row">
                  <span class="pill" :class="{ active: jsonDiffRightAnalysis?.status === 'valid' }">{{ jsonDiffRightAnalysis?.summary || 'Empty' }}</span>
                  <span class="field-help">{{ jsonDiffRightAnalysis?.help }}</span>
                </div>
              </section>
            </div>

            <div v-else-if="specializedLayoutKind === 'text-diff'" class="special-form special-form--compare">
              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('left_text', 'Text A') }}</label>
                  <div v-if="fieldActionItemsByName('left_text').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('left_text')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.left_text" :placeholder="fieldPlaceholder('left_text', 'Left text block')" :auto-size="{ minRows: 12, maxRows: 20 }" />
                <div class="field-help">Used as the baseline document in the diff result.</div>
              </section>

              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('right_text', 'Text B') }}</label>
                  <div v-if="fieldActionItemsByName('right_text').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('right_text')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.right_text" :placeholder="fieldPlaceholder('right_text', 'Right text block')" :auto-size="{ minRows: 12, maxRows: 20 }" />
                <div class="field-help">Compared against Text A to produce similarity and unified diff lines.</div>
              </section>
            </div>

            <div v-else-if="specializedLayoutKind === 'cron-generate'" class="special-form">
              <div class="special-form__cron-grid">
                <section v-for="name in ['minute', 'hour', 'day', 'month', 'weekday']" :key="name" class="special-form__panel">
                  <label>{{ fieldLabel(name) }}</label>
                  <a-input v-model="toolForm[name]" :placeholder="fieldPlaceholder(name, '*')" />
                  <div v-if="fieldHelpText(name)" class="field-help">{{ fieldHelpText(name) }}</div>
                </section>
              </div>
            </div>

            <div v-else-if="specializedLayoutKind === 'cron-expression'" class="special-form">
              <section class="special-form__panel special-form__panel--wide">
                <div class="special-form__label-row">
                  <label>{{ fieldLabel('expression', 'Crontab Expression') }}</label>
                  <div v-if="fieldActionItemsByName('expression').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('expression')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <a-textarea v-model="toolForm.expression" :placeholder="fieldPlaceholder('expression', '0 */2 * * *')" :auto-size="{ minRows: 4, maxRows: 8 }" />
                <div class="special-form__meta-row">
                  <span class="pill" :class="{ active: cronPreviewStatus.tone === 'success' }">{{ cronPreviewStatus.text }}</span>
                  <span class="field-help">{{ cronPreviewStatus.help }}</span>
                </div>
              </section>
              <div v-if="currentTool?.name === 'cron_next_runs'" class="special-form__inline-grid">
                <section class="special-form__panel">
                  <label>{{ fieldLabel('count', 'Count') }}</label>
                  <a-input-number v-model="toolForm.count" :min="fieldMin('count')" :max="fieldMax('count')" style="width: 100%" />
                </section>
                <section class="special-form__panel">
                  <label>{{ fieldLabel('timezone', 'Timezone') }}</label>
                  <a-input v-model="toolForm.timezone" :placeholder="fieldPlaceholder('timezone', 'Asia/Shanghai')" />
                </section>
              </div>
            </div>

            <div v-else-if="specializedLayoutKind === 'image-base64'" class="special-form special-form--two-columns">
              <section class="special-form__panel">
                <label>{{ fieldLabel('mode', 'Mode') }}</label>
                <a-select v-model="toolForm.mode">
                  <a-option v-for="option in fieldOptions('mode')" :key="String(option.value)" :value="option.value" :label="option.label" />
                </a-select>

                <div class="special-form__label-row">
                  <label>{{ fieldLabel('image_data', 'Image / Base64 Data') }}</label>
                  <div v-if="fieldActionItemsByName('image_data').length" class="field-actions">
                    <a-button v-for="action in fieldActionItemsByName('image_data')" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                  </div>
                </div>
                <div class="upload-wrap">
                  <a-textarea v-model="toolForm.image_data" :placeholder="fieldPlaceholder('image_data', 'Paste a data URL, raw Base64, or upload an image')" :auto-size="{ minRows: 10, maxRows: 18 }" />
                  <input :ref="element => registerUploadInput('image_data', element as HTMLInputElement | null)" type="file" class="hidden-input" accept="image/*" @change="event => handleImagePicked('image_data', event)" />
                  <a-button size="small" @click="triggerImagePicker('image_data')">Upload Image</a-button>
                </div>

                <div v-if="toolForm.mode === 'image_to_base64'" class="switch-row">
                  <a-switch v-model="toolForm.include_prefix" />
                  <span>{{ toolForm.include_prefix ? 'Keep data URL prefix' : 'Return pure Base64' }}</span>
                </div>
              </section>

              <section class="special-form__panel">
                <div class="special-form__label-row">
                  <label>Input Preview</label>
                  <span class="pill" :class="{ active: Boolean(activeUploadPreviewUrl) }">{{ imageInputModeLabel }}</span>
                </div>
                <div v-if="activeUploadPreviewUrl" class="input-preview input-preview--static">
                  <img :src="activeUploadPreviewUrl" alt="preview" class="input-preview__image" />
                  <div class="input-preview__meta">
                    <span class="pill active">{{ imageInputModeLabel }}</span>
                    <span class="pill">{{ activeUploadDescription }}</span>
                  </div>
                </div>
                <div v-else class="empty">Upload an image, paste a data URL, or provide recognizable Base64 to render a preview here.</div>
              </section>
            </div>

            <div v-else class="form-grid">
              <div v-for="field in currentTool.fields" :key="field.name" class="field" :class="{ full: isFullWidthField(field.type) }">
                <label>{{ field.label }}</label>
                <div class="field-stack">
                <a-input v-if="field.type === 'text'" v-model="toolForm[field.name]" :placeholder="field.placeholder" />
                <a-textarea v-else-if="field.type === 'textarea'" v-model="toolForm[field.name]" :placeholder="field.placeholder" :auto-size="{ minRows: field.rows || 4, maxRows: 12 }" />
                <a-input-number v-else-if="field.type === 'number'" v-model="toolForm[field.name]" :min="field.min" :max="field.max" style="width: 100%" />
                <a-select v-else-if="field.type === 'select'" v-model="toolForm[field.name]">
                  <a-option v-for="option in field.options || []" :key="String(option.value)" :value="option.value" :label="option.label" />
                </a-select>
                <a-select v-else-if="field.type === 'multi-select'" v-model="toolForm[field.name]" multiple allow-clear>
                  <a-option v-for="option in field.options || []" :key="String(option.value)" :value="option.value" :label="option.label" />
                </a-select>
                <div v-else-if="field.type === 'switch'" class="switch-row"><a-switch v-model="toolForm[field.name]" /><span>{{ toolForm[field.name] ? '开启' : '关闭' }}</span></div>
                <a-textarea v-else-if="field.type === 'json'" v-model="toolForm[field.name]" :placeholder="field.placeholder || '请输入 JSON 内容'" :auto-size="{ minRows: field.rows || 5, maxRows: 12 }" />
                <div v-else-if="field.type === 'upload-base64'" class="upload-wrap">
                  <a-textarea v-model="toolForm[field.name]" :placeholder="field.placeholder || '支持粘贴 Base64 / Data URL，或直接上传图片'" :auto-size="{ minRows: 5, maxRows: 12 }" />
                  <input :ref="element => registerUploadInput(field.name, element as HTMLInputElement | null)" type="file" class="hidden-input" accept="image/*" @change="event => handleImagePicked(field.name, event)" />
                  <a-button size="small" @click="triggerImagePicker(field.name)">上传图片</a-button>
                </div>
                <div v-if="fieldActionItems(field).length" class="field-actions">
                  <a-button v-for="action in fieldActionItems(field)" :key="action.key" size="mini" @click="action.run()">{{ action.label }}</a-button>
                </div>
                <div v-if="field.type === 'upload-base64' && fieldPreviewImageUrl(field.name)" class="input-preview">
                  <img :src="fieldPreviewImageUrl(field.name)" alt="preview" class="input-preview__image" />
                  <div class="input-preview__meta">
                    <span class="pill active">{{ imageInputModeLabel }}</span>
                    <span class="pill">{{ describeImageInput(field.name) }}</span>
                  </div>
                </div>
                </div>
                <div v-if="field.help_text" class="field-help">{{ field.help_text }}</div>
                <div v-else-if="field.type === 'upload-base64' && toolForm[field.name] && !fieldPreviewImageUrl(field.name)" class="field-help field-help--preview-tip">Preview works best when the value keeps a `data:image/...;base64,` prefix.</div>
                <!--
                <div v-else-if="field.type === 'upload-base64' && toolForm[field.name] && !fieldPreviewImageUrl(field.name)" class="field-help">璇ュ瓧娈靛凡鍐欏叆鍐呭锛屽鏋滄槸绾?Base64 锛屽缓璁繚鐣?data:image/...;base64, 鍓嶇紑浠ヨ幏寰楀嵆鏃堕瑙堛€?/div>
                -->
              </div>
            </div>

            <div class="panel sub-panel">
              <div v-if="!projectReady" class="empty">{{ projectLockMessage }}</div>
              <a-select v-model="selectedTagIds" multiple allow-clear placeholder="关联已有标签" :disabled="!projectReady">
                <a-option v-for="tag in tags" :key="tag.id" :value="tag.id" :label="tag.name">{{ tag.name }}</a-option>
              </a-select>
              <a-input v-model="tagNamesText" placeholder="新增标签，多个标签请用逗号分隔" :disabled="!projectReady" />
              <div class="action-row">
                <div class="switch-row"><span>保存到记录</span><a-switch v-model="saveRecord" :disabled="!projectReady" /></div>
                <a-space>
                  <a-button @click="resetToolForm(currentTool)">重置</a-button>
                  <a-button type="primary" :loading="executing" :disabled="!projectReady" @click="executeToolRun"><template #icon><icon-play-arrow /></template>运行工具</a-button>
                </a-space>
              </div>
            </div>
          </section>

          <section class="panel tool-pane">
            <div class="section-title">执行结果</div>
            <template v-if="projectReady && executionOutput">
              <div class="result-summary">{{ executionOutput.summary || '执行完成' }}</div>
              <div class="result-actions">
                <a-space wrap>
                  <a-button v-if="canCopyResult" size="small" @click="copyResultContent"><template #icon><icon-copy /></template>复制结果</a-button>
                  <a-button v-if="canDownloadResult" size="small" @click="downloadResultContent"><template #icon><icon-download /></template>下载结果</a-button>
                  <a-button v-if="resultKind === 'json-tree'" size="small" @click="expandAllJson">展开树</a-button>
                  <a-button v-if="resultKind === 'json-tree'" size="small" @click="collapseAllJson">收起树</a-button>
                  <a-button v-if="resultKind === 'image' && resultImageUrl" size="small" @click="downloadResultImage"><template #icon><icon-download /></template>下载图片</a-button>
                </a-space>
              </div>
              <div v-if="resultSpecialLayout === 'jsonpath' && jsonPathResult" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Match Count</span>
                    <strong class="special-result__value">{{ jsonPathResult.count }}</strong>
                    <span class="special-result__help">JSONPath returned {{ jsonPathResult.count }} matched value(s).</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Expression</span>
                    <strong class="special-result__value">{{ jsonPathResult.path || 'Not provided' }}</strong>
                    <span class="special-result__help">Executed against the current JSON payload.</span>
                  </article>
                </div>
                <div v-if="jsonPathResult.matches.length" class="special-result__list">
                  <article v-for="(item, index) in jsonPathResult.matches" :key="`jsonpath-${index}`" class="special-result__list-item">
                    <div class="special-result__list-head">
                      <strong>Match {{ index + 1 }}</strong>
                    </div>
                    <pre class="result-inline-block">{{ formatStructuredValue(item) }}</pre>
                  </article>
                </div>
                <div v-else class="empty">No values matched the current JSONPath expression.</div>
              </div>

              <div v-else-if="resultSpecialLayout === 'json-validate' && jsonValidateResult" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card" :class="{ 'is-success': jsonValidateResult.valid, 'is-warning': !jsonValidateResult.valid }">
                    <span class="special-result__label">Validation</span>
                    <strong class="special-result__value">{{ jsonValidateResult.valid ? 'Valid JSON' : 'Invalid JSON' }}</strong>
                    <span class="special-result__help">{{ jsonValidateResult.valid ? 'The payload passed JSON parsing successfully.' : (jsonValidateResult.message || 'JSON validation failed.') }}</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">{{ jsonValidateResult.valid ? 'Detected Type' : 'Error Position' }}</span>
                    <strong class="special-result__value">{{ jsonValidateResult.valid ? (jsonValidateResult.type || 'unknown') : `Line ${jsonValidateResult.line || '-'} / Column ${jsonValidateResult.column || '-'}` }}</strong>
                    <span class="special-result__help">{{ jsonValidateResult.valid ? 'Returned from the backend JSON parser.' : 'Use the position to jump back to the malformed input.' }}</span>
                  </article>
                </div>
                <article v-if="!jsonValidateResult.valid" class="special-result__list-item">
                  <div class="special-result__list-head">
                    <strong>Error Message</strong>
                  </div>
                  <pre class="result-inline-block">{{ jsonValidateResult.message || 'Unknown JSON validation error.' }}</pre>
                </article>
              </div>

              <div v-else-if="resultSpecialLayout === 'json-diff' && jsonDiffResult" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card" :class="{ 'is-success': !jsonDiffResult.different, 'is-warning': jsonDiffResult.different }">
                    <span class="special-result__label">Compare Status</span>
                    <strong class="special-result__value">{{ jsonDiffResult.different ? 'Differences Found' : 'No Differences' }}</strong>
                    <span class="special-result__help">{{ jsonDiffResult.different ? `Detected ${jsonDiffResult.count} difference(s).` : 'Both JSON payloads are equivalent.' }}</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Difference Count</span>
                    <strong class="special-result__value">{{ jsonDiffResult.count }}</strong>
                    <span class="special-result__help">Paths are listed below in execution order.</span>
                  </article>
                </div>
                <div v-if="jsonDiffResult.diffs.length" class="diff-list">
                  <article v-for="(diff, index) in jsonDiffResult.diffs" :key="`${diff.path}-${index}`" class="diff-item">
                    <div class="diff-item__head">
                      <strong>{{ diff.path }}</strong>
                      <span class="pill active">{{ diff.type }}</span>
                    </div>
                    <div class="diff-item__grid">
                      <div class="diff-item__value">
                        <span>Left</span>
                        <pre class="result-inline-block">{{ formatStructuredValue(diff.left) }}</pre>
                      </div>
                      <div class="diff-item__value">
                        <span>Right</span>
                        <pre class="result-inline-block">{{ formatStructuredValue(diff.right) }}</pre>
                      </div>
                    </div>
                  </article>
                </div>
                <div v-else class="empty">No structural or value differences were found.</div>
              </div>

              <div v-else-if="resultSpecialLayout === 'text-diff' && textDiffResult" class="special-result">
                <div class="special-result__cards special-result__cards--three">
                  <article class="special-result__card" :class="{ 'is-success': textDiffResult.same, 'is-warning': !textDiffResult.same }">
                    <span class="special-result__label">Compare Status</span>
                    <strong class="special-result__value">{{ textDiffResult.same ? 'Texts Match' : 'Differences Found' }}</strong>
                    <span class="special-result__help">{{ textDiffResult.same ? 'Both text blocks are identical.' : `Unified diff returned ${textDiffResult.diffLines.length} line(s).` }}</span>
                  </article>
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Similarity</span>
                    <strong class="special-result__value">{{ textDiffResult.similarity }}%</strong>
                    <span class="special-result__help">Calculated by the backend sequence matcher.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Line Counts</span>
                    <strong class="special-result__value">{{ textDiffResult.leftLineCount }} / {{ textDiffResult.rightLineCount }}</strong>
                    <span class="special-result__help">Text A lines on the left, Text B lines on the right.</span>
                  </article>
                </div>
                <pre class="result-block">{{ textDiffResult.diffLines.length ? textDiffResult.diffLines.join('\n') : 'No unified diff output because the two texts are identical.' }}</pre>
              </div>

              <div v-else-if="resultSpecialLayout === 'regex-test' && regexTestResult" class="special-result">
                <div class="special-result__cards special-result__cards--three">
                  <article class="special-result__card" :class="{ 'is-success': regexTestResult.matched, 'is-warning': !regexTestResult.matched }">
                    <span class="special-result__label">Match Status</span>
                    <strong class="special-result__value">{{ regexTestResult.matched ? 'Matched' : 'No Match' }}</strong>
                    <span class="special-result__help">{{ regexTestResult.matched ? 'At least one result matched the current pattern.' : 'No result matched the current regex expression.' }}</span>
                  </article>
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Match Count</span>
                    <strong class="special-result__value">{{ regexTestResult.count }}</strong>
                    <span class="special-result__help">Total matches returned by the backend regex engine.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Pattern</span>
                    <strong class="special-result__value">{{ activeResultInput.pattern || 'Not captured' }}</strong>
                    <span class="special-result__help">Flags: {{ Array.isArray(activeResultInput.flags) && activeResultInput.flags.length ? activeResultInput.flags.join(', ') : 'none' }}</span>
                  </article>
                </div>
                <div v-if="regexTestResult.matches.length" class="special-result__list">
                  <article v-for="item in regexTestResult.matches" :key="item.key" class="special-result__list-item">
                    <div class="special-result__list-head">
                      <strong>{{ item.match }}</strong>
                      <span class="pill active">{{ item.start }} - {{ item.end }}</span>
                    </div>
                    <div class="diff-item__grid">
                      <div class="diff-item__value">
                        <span>Capture Groups</span>
                        <pre class="result-inline-block">{{ item.groups.length ? formatStructuredValue(item.groups) : 'No capture groups returned.' }}</pre>
                      </div>
                      <div class="diff-item__value">
                        <span>Named Groups</span>
                        <pre class="result-inline-block">{{ Object.keys(item.groupDict).length ? formatStructuredValue(item.groupDict) : 'No named groups returned.' }}</pre>
                      </div>
                    </div>
                  </article>
                </div>
                <div v-else class="empty">No matches were returned for the current regex and input text.</div>
              </div>

              <div v-else-if="resultSpecialLayout === 'json-text' && jsonTextResult" class="special-result">
                <div class="special-result__cards special-result__cards--three">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Output Format</span>
                    <strong class="special-result__value">{{ jsonTextResultFormat }}</strong>
                    <span class="special-result__help">Generated from the current JSON payload.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Line Count</span>
                    <strong class="special-result__value">{{ jsonTextResultMetrics.lineCount }}</strong>
                    <span class="special-result__help">Useful before copying into editors or configuration files.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Characters</span>
                    <strong class="special-result__value">{{ jsonTextResultMetrics.charCount }}</strong>
                    <span class="special-result__help">Total output size of the converted text.</span>
                  </article>
                </div>
                <pre class="result-block">{{ jsonTextResult }}</pre>
              </div>

              <div v-else-if="resultSpecialLayout === 'json-to-csv' && csvResultText" class="special-result">
                <div class="special-result__cards special-result__cards--three">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Columns</span>
                    <strong class="special-result__value">{{ csvColumns.length }}</strong>
                    <span class="special-result__help">Flattened keys collected from the JSON objects.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Rows</span>
                    <strong class="special-result__value">{{ csvRowCount }}</strong>
                    <span class="special-result__help">CSV data rows excluding the header line.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Characters</span>
                    <strong class="special-result__value">{{ csvResultText.length }}</strong>
                    <span class="special-result__help">Ready to copy into spreadsheets or fixtures.</span>
                  </article>
                </div>
                <div v-if="csvColumns.length" class="result-meta">
                  <span v-for="column in csvColumns" :key="column" class="pill active">{{ column }}</span>
                </div>
                <pre class="result-block">{{ csvResultText }}</pre>
              </div>

              <div v-else-if="resultSpecialLayout === 'cron-generate' && cronGeneratedExpression" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Generated Expression</span>
                    <strong class="special-result__value">{{ cronGeneratedExpression }}</strong>
                    <span class="special-result__help">Ready to copy into scheduled jobs or parsers.</span>
                  </article>
                </div>
                <pre class="tool-special-panel__code">{{ cronGeneratedExpression }}</pre>
              </div>

              <div v-else-if="resultSpecialLayout === 'cron-parse' && cronParseResult" class="special-result">
                <div class="special-result__cards special-result__cards--five">
                  <article v-for="item in [
                    { label: 'Minute', value: cronParseResult.minute },
                    { label: 'Hour', value: cronParseResult.hour },
                    { label: 'Day', value: cronParseResult.day },
                    { label: 'Month', value: cronParseResult.month },
                    { label: 'Weekday', value: cronParseResult.weekday }
                  ]" :key="item.label" class="special-result__card">
                    <span class="special-result__label">{{ item.label }}</span>
                    <strong class="special-result__value">{{ item.value }}</strong>
                    <span class="special-result__help">{{ cronParseResult.expression }}</span>
                  </article>
                </div>
              </div>

              <div v-else-if="resultSpecialLayout === 'cron-next-runs'" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Upcoming Runs</span>
                    <strong class="special-result__value">{{ cronNextRunsResult.length }}</strong>
                    <span class="special-result__help">Calculated using the selected timezone.</span>
                  </article>
                  <article v-if="resultMetadataEntries.length" class="special-result__card">
                    <span class="special-result__label">{{ resultMetadataEntries[0].label }}</span>
                    <strong class="special-result__value">{{ resultMetadataEntries[0].value }}</strong>
                    <span class="special-result__help">Timezone used for the next-run calculation.</span>
                  </article>
                </div>
                <div v-if="cronNextRunsResult.length" class="special-result__list">
                  <article v-for="(item, index) in cronNextRunsResult" :key="`${item}-${index}`" class="special-result__list-item">
                    <div class="special-result__list-head">
                      <strong>Run {{ index + 1 }}</strong>
                    </div>
                    <pre class="result-inline-block">{{ item }}</pre>
                  </article>
                </div>
                <div v-else class="empty">No future run times were returned.</div>
              </div>

              <div v-else-if="resultSpecialLayout === 'cron-validate' && cronValidateResult" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card" :class="{ 'is-success': cronValidateResult.valid, 'is-warning': !cronValidateResult.valid }">
                    <span class="special-result__label">Validation</span>
                    <strong class="special-result__value">{{ cronValidateResult.valid ? 'Valid Expression' : 'Invalid Expression' }}</strong>
                    <span class="special-result__help">{{ cronValidateResult.valid ? 'The expression passed cron validation.' : (cronValidateResult.message || 'Cron validation failed.') }}</span>
                  </article>
                </div>
              </div>

              <div v-else-if="resultSpecialLayout === 'image-base64'" class="special-result">
                <div class="special-result__cards">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Conversion Mode</span>
                    <strong class="special-result__value">{{ imageBase64ResultObject ? 'Base64 -> Image' : 'Image -> Base64' }}</strong>
                    <span class="special-result__help">{{ imageBase64ResultObject ? 'Binary output was reconstructed into an image preview.' : 'Text output is ready to copy or download.' }}</span>
                  </article>
                  <article v-if="imageBase64ResultObject" class="special-result__card">
                    <span class="special-result__label">Image Info</span>
                    <strong class="special-result__value">{{ imageBase64ResultObject.mime_type || 'image/png' }}</strong>
                    <span class="special-result__help">{{ formatBytes(imageBase64ResultObject.size) }}</span>
                  </article>
                  <article v-else class="special-result__card">
                    <span class="special-result__label">Output Length</span>
                    <strong class="special-result__value">{{ imageBase64ResultText.length }}</strong>
                    <span class="special-result__help">Character count of the generated Base64 payload.</span>
                  </article>
                </div>
                <div v-if="imageBase64ResultPreviewUrl" class="image-result">
                  <img :src="imageBase64ResultPreviewUrl" alt="converted" class="result-image" />
                </div>
                <pre v-if="imageBase64ResultText" class="result-block">{{ imageBase64ResultText }}</pre>
                <pre v-else-if="imageBase64ResultObject" class="result-block">{{ formattedResult }}</pre>
              </div>

              <div v-else-if="resultSpecialLayout === 'aes-encrypt' && aesEncryptResult" class="special-result">
                <div class="special-result__cards special-result__cards--three">
                  <article class="special-result__card is-success">
                    <span class="special-result__label">Mode</span>
                    <strong class="special-result__value">{{ aesEncryptResult.mode || 'AES' }}</strong>
                    <span class="special-result__help">Encryption mode returned by the backend executor.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">Cipher Length</span>
                    <strong class="special-result__value">{{ aesEncryptResult.cipherText.length }}</strong>
                    <span class="special-result__help">Character count of the Base64 cipher text.</span>
                  </article>
                  <article class="special-result__card">
                    <span class="special-result__label">IV</span>
                    <strong class="special-result__value">{{ aesEncryptResult.iv ? 'Included' : 'Not used' }}</strong>
                    <span class="special-result__help">{{ aesEncryptResult.iv ? 'CBC mode returns an initialization vector.' : 'ECB mode does not include an IV.' }}</span>
                  </article>
                </div>
                <div class="special-result__list">
                  <article class="special-result__list-item">
                    <div class="special-result__list-head">
                      <strong>Cipher Text</strong>
                    </div>
                    <pre class="result-inline-block">{{ aesEncryptResult.cipherText }}</pre>
                  </article>
                  <article v-if="aesEncryptResult.iv" class="special-result__list-item">
                    <div class="special-result__list-head">
                      <strong>Initialization Vector</strong>
                    </div>
                    <pre class="result-inline-block">{{ aesEncryptResult.iv }}</pre>
                  </article>
                </div>
              </div>

              <div v-else-if="resultKind === 'image' && resultImageUrl" class="image-result">
                <img :src="resultImageUrl" alt="result" class="result-image" />
                <div v-if="imageResultMeta.length" class="result-meta">
                  <span v-for="item in imageResultMeta" :key="item.label" class="pill">{{ item.label }}：{{ item.value }}</span>
                </div>
              </div>
              <div v-else-if="resultKind === 'json-tree'" class="tree-result">
                <a-tree
                  v-if="jsonTreeData.length"
                  :data="jsonTreeData"
                  block-node
                  show-line
                  :expanded-keys="jsonExpandedKeys"
                  :field-names="{ key: 'key', title: 'title', children: 'children' }"
                  @expand="handleJsonExpand"
                />
                <pre class="result-block">{{ formattedResult }}</pre>
              </div>
              <div v-else class="result-stack">
                <img v-if="previewImageUrl" :src="previewImageUrl" alt="preview" class="result-image result-image--preview" />
                <pre class="result-block">{{ formattedResult }}</pre>
              </div>
              <div v-if="resultMetadataEntries.length" class="result-meta">
                <span v-for="item in resultMetadataEntries" :key="item.label" class="pill">{{ item.label }}：{{ item.value }}</span>
              </div>
              <div v-if="lastExecution?.record" class="hero__meta">
                <a-button size="small" @click="copyText(lastExecution.record.reference_placeholder_api, '已复制 API 引用')"><template #icon><icon-copy /></template>API 引用</a-button>
                <a-button size="small" @click="copyText(lastExecution.record.reference_placeholder_ui, '已复制 UI 引用')"><template #icon><icon-copy /></template>UI 引用</a-button>
              </div>
            </template>
            <div v-else class="empty">{{ projectReady ? '点击运行工具后，结果会显示在这里。' : projectLockMessage }}</div>
          </section>
        </div>
      </div>
    </a-modal>

    <a-drawer :visible="historyVisible" width="1100px" title="数据工厂记录与统计" @cancel="historyVisible = false">
      <a-tabs v-model:active-key="historyTab">
        <a-tab-pane key="records" title="使用记录">
          <div class="history-filters">
            <a-input-search v-model="recordFilters.search" allow-clear placeholder="搜索工具、标签或结果预览" :disabled="!projectReady" @search="searchRecords" @clear="searchRecords" />
            <a-select v-model="recordFilters.category" :disabled="!projectReady" @change="searchRecords">
              <a-option value="all" label="全部分类" />
              <a-option v-for="category in catalog.categories" :key="category.category" :value="category.category" :label="category.name" />
            </a-select>
            <a-select v-model="recordFilters.scenario" :disabled="!projectReady" @change="searchRecords">
              <a-option value="all" label="全部场景" />
              <a-option v-for="scenario in catalog.scenarios" :key="scenario.scenario" :value="scenario.scenario" :label="scenario.name" />
            </a-select>
            <a-select v-model="recordFilters.saved" :disabled="!projectReady" @change="searchRecords">
              <a-option value="all" label="全部记录" />
              <a-option value="saved" label="仅已保存" />
              <a-option value="temp" label="仅临时结果" />
            </a-select>
          </div>
          <a-table :data="projectReady ? records : []" :loading="projectReady ? loadingRecords : false" :pagination="projectReady ? recordPagination : false" row-key="id" @page-change="handleRecordPageChange" @page-size-change="handleRecordPageSizeChange">
            <template #columns>
              <a-table-column title="ID" data-index="id" :width="80" />
              <a-table-column title="工具" :width="220"><template #cell="{ record }"><div class="record-tool"><strong>{{ record.tool_display_name }}</strong><span>{{ record.category_display }} / {{ record.scenario_display }}</span></div></template></a-table-column>
              <a-table-column title="标签" :width="220"><template #cell="{ record }"><a-space wrap size="mini"><a-tag v-for="tag in record.tags" :key="tag.id" :color="tag.color || 'arcoblue'">{{ tag.name }}</a-tag></a-space></template></a-table-column>
              <a-table-column title="结果预览" data-index="preview" ellipsis tooltip />
              <a-table-column title="创建时间" :width="180"><template #cell="{ record }">{{ formatDate(record.created_at) }}</template></a-table-column>
              <a-table-column title="操作" :width="280"><template #cell="{ record }"><a-space wrap><a-button size="mini" :disabled="!projectReady" @click="showRecordResult(record)">查看</a-button><a-button size="mini" :disabled="!projectReady" @click="copyText(record.reference_placeholder_api, '已复制 API 记录引用')">API</a-button><a-button size="mini" :disabled="!projectReady" @click="copyText(record.reference_placeholder_ui, '已复制 UI 记录引用')">UI</a-button><a-popconfirm content="确定删除这条记录吗？" @ok="deleteRecord(record.id)"><a-button size="mini" status="danger" :disabled="!projectReady">删除</a-button></a-popconfirm></a-space></template></a-table-column>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="stats" title="统计概览">
          <div class="insight-grid insight-grid--drawer">
            <div class="panel"><div class="section-title">分类使用统计</div><div class="metric-list"><div v-for="item in categoryBreakdown" :key="item.key" class="metric"><div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div><div class="metric__track"><span class="metric__bar" :style="{ width: `${item.percent}%` }"></span></div></div></div></div>
            <div class="panel"><div class="section-title">场景使用统计</div><div class="metric-list"><div v-for="item in scenarioBreakdown" :key="item.key" class="metric"><div class="metric__head"><span>{{ item.name }}</span><strong>{{ item.total }}</strong></div><div class="metric__track"><span class="metric__bar metric__bar--soft" :style="{ width: `${item.percent}%` }"></span></div></div></div></div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <DataFactoryTagManager v-model="tagManagerVisible" :project-id="projectId" @updated="handleTagsUpdated" />
    <DataFactoryReferencePicker
      v-model="referencePickerVisible"
      :project-id="projectId"
      :mode="referencePickerMode"
      :title="referencePickerTitle"
      @select="handleReferenceSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconArrowRight, IconCheckCircle, IconClockCircle, IconCodeBlock, IconCopy, IconDownload, IconFile, IconFire, IconFontColors, IconHistory, IconLock, IconPlayArrow, IconRefresh, IconTags, IconTool, IconUserGroup } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { dataFactoryApi } from '../api'
import DataFactoryReferencePicker from '../components/DataFactoryReferencePicker.vue'
import DataFactoryTagManager from '../components/DataFactoryTagManager.vue'
import type { DataFactoryCatalog, DataFactoryCategory, DataFactoryCategoryKey, DataFactoryExecuteResult, DataFactoryFieldType, DataFactoryRecord, DataFactoryReferenceMode, DataFactoryScenarioKey, DataFactoryStatistics, DataFactoryTag, DataFactoryTool, DataFactoryToolField } from '../types'
import { buildDataFactoryPlaceholder, DATA_FACTORY_SCENARIO_LABELS, extractDataFactoryData } from '../types'

type ViewMode = 'category' | 'scenario'
type SavedFilter = 'all' | 'saved' | 'temp'
type CategoryFilter = DataFactoryCategoryKey | 'all'
type ScenarioFilter = DataFactoryScenarioKey | 'all'
type JsonTreeNode = { key: string; title: string; children?: JsonTreeNode[] }
type CategoryCard = DataFactoryCategory & { toolCount: number; previewTools: DataFactoryTool[]; scenarioNames: string[] }
type VisibleCategory = DataFactoryCategory & { visibleTools: DataFactoryTool[] }
type ToolPreset = { key: string; label: string; values?: Record<string, any>; action?: () => void }
type ToolFieldAction = { key: string; label: string; run: () => void }
type ToolWorkbenchCard = { key: string; label: string; value: string; help: string; tone?: 'default' | 'success' | 'warning' }
type ResultSpecialLayout =
  | 'generic'
  | 'json-validate'
  | 'jsonpath'
  | 'json-diff'
  | 'text-diff'
  | 'regex-test'
  | 'json-text'
  | 'json-to-csv'
  | 'cron-generate'
  | 'cron-parse'
  | 'cron-next-runs'
  | 'cron-validate'
  | 'image-base64'
  | 'aes-encrypt'
type JsonInputAnalysis = {
  status: 'empty' | 'valid' | 'invalid'
  charCount: number
  lineCount: number
  summary: string
  help: string
}

const emptyStatistics = (): DataFactoryStatistics => ({ total_records: 0, saved_records: 0, category_stats: [], scenario_stats: [], tag_stats: [], recent_records: [] })
const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id ?? null)
const projectName = computed(() => projectStore.currentProject?.name || '未选择项目')
const projectReady = computed(() => Boolean(projectId.value))
const projectLockMessage = '未选择项目时可浏览全部工具，执行、记录和标签管理暂不可用。'

const categoryIcons: Record<DataFactoryCategoryKey, any> = { string: IconFontColors, encoding: IconCodeBlock, random: IconFire, encryption: IconLock, test_data: IconUserGroup, json: IconFile, crontab: IconClockCircle }
const scenarioIcons: Record<DataFactoryScenarioKey, any> = { data_generation: IconFire, format_conversion: IconTool, data_validation: IconCheckCircle, encryption_decryption: IconLock }

const viewMode = ref<ViewMode>('category')
const historyVisible = ref(false)
const historyTab = ref('records')
const toolDialogVisible = ref(false)
const tagManagerVisible = ref(false)
const referencePickerVisible = ref(false)
const referencePickerMode = ref<DataFactoryReferenceMode>('api')
const catalog = ref<DataFactoryCatalog>({ categories: [], scenarios: [], tools: [] })
const tags = ref<DataFactoryTag[]>([])
const statistics = ref<DataFactoryStatistics>(emptyStatistics())
const records = ref<DataFactoryRecord[]>([])
const loadingRecords = ref(false)
const executing = ref(false)
const lastExecution = ref<DataFactoryExecuteResult | null>(null)
const toolKeyword = ref('')
const selectedScenario = ref<ScenarioFilter>('all')
const focusedCategory = ref<CategoryFilter>('all')
const currentToolName = ref('')
const toolForm = ref<Record<string, any>>({})
const selectedTagIds = ref<number[]>([])
const tagNamesText = ref('')
const saveRecord = ref(true)
const uploadInputs = new Map<string, HTMLInputElement>()
const toolWorkspaceSection = ref<HTMLElement | null>(null)

const recordFilters = reactive({ search: '', saved: 'all' as SavedFilter, category: 'all' as CategoryFilter, scenario: 'all' as ScenarioFilter })
const recordPagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const matchKeyword = (tool: DataFactoryTool, keyword: string) => !keyword || [tool.display_name, tool.name, tool.description].some(value => String(value || '').toLowerCase().includes(keyword))
const categoryName = (category: DataFactoryCategoryKey) => catalog.value.categories.find(item => item.category === category)?.name || category
const scenarioLabel = (scenario: DataFactoryScenarioKey) => DATA_FACTORY_SCENARIO_LABELS[scenario] || scenario
const categoryIcon = (category: DataFactoryCategoryKey) => categoryIcons[category] || IconTool
const scenarioIcon = (scenario: DataFactoryScenarioKey) => scenarioIcons[scenario] || IconTool
const normalizeErrorMessage = (error: any, fallback: string) => error?.error || error?.response?.data?.message || error?.message || fallback
const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const cloneValue = <T,>(value: T): T => Array.isArray(value) ? ([...value] as T) : value && typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value

const sampleJsonObjectText = JSON.stringify(
  {
    requestId: 'REQ-20260406-001',
    user: {
      id: 1001,
      name: 'Alice',
      roles: ['tester', 'admin'],
    },
    items: [
      { sku: 'FT-001', qty: 2, passed: true },
      { sku: 'FT-002', qty: 1, passed: false },
    ],
    meta: {
      total: 2,
      env: 'staging',
    },
  },
  null,
  2
)

const sampleJsonArrayText = JSON.stringify(
  [
    { id: 1, name: 'Login', owner: 'QA', status: 'ready' },
    { id: 2, name: 'Checkout', owner: 'Dev', status: 'draft' },
  ],
  null,
  2
)

const sampleJsonDiffLeftText = JSON.stringify(
  {
    project: 'FlyTest',
    version: '1.0.0',
    features: ['api', 'ui'],
    enabled: true,
  },
  null,
  2
)

const sampleJsonDiffRightText = JSON.stringify(
  {
    project: 'FlyTest',
    version: '1.1.0',
    features: ['api', 'ui', 'app'],
    enabled: true,
  },
  null,
  2
)

const sampleTextDiffLeftText = [
  'Suite: Login smoke',
  '1. Open login page',
  '2. Enter username',
  '3. Enter password',
  '4. Click submit',
  '5. Expect dashboard visible',
].join('\n')

const sampleTextDiffRightText = [
  'Suite: Login smoke',
  '1. Open sign-in page',
  '2. Enter username',
  '3. Enter password',
  '4. Click sign in',
  '5. Expect dashboard visible',
].join('\n')

const sampleRegexCaseCodeText = [
  'FT-LOGIN-001',
  'FT-CHECKOUT-102',
  'invalid_case',
  'FT-ORDER-900',
].join('\n')

const sampleRegexEmailText = [
  'qa@flytest.io',
  'ops@example.com',
  'invalid-email',
  'automation@test.local',
].join('\n')

const cronGeneratePresets = [
  { key: 'cron-generate-every-5m', label: 'Every 5 min', values: { minute: '*/5', hour: '*', day: '*', month: '*', weekday: '*' } },
  { key: 'cron-generate-daily-9', label: 'Daily 09:00', values: { minute: '0', hour: '9', day: '*', month: '*', weekday: '*' } },
  { key: 'cron-generate-weekday-10', label: 'Weekdays 10:00', values: { minute: '0', hour: '10', day: '*', month: '*', weekday: '1-5' } },
  { key: 'cron-generate-nightly', label: 'Nightly 23:30', values: { minute: '30', hour: '23', day: '*', month: '*', weekday: '*' } },
] satisfies Array<{ key: string; label: string; values: Record<string, string> }>

const cronExpressionPresets = [
  { key: 'cron-expression-every-5m', label: '*/5 * * * *', values: { expression: '*/5 * * * *' } },
  { key: 'cron-expression-daily-9', label: '0 9 * * *', values: { expression: '0 9 * * *' } },
  { key: 'cron-expression-weekday-10', label: '0 10 * * 1-5', values: { expression: '0 10 * * 1-5' } },
  { key: 'cron-expression-nightly', label: '30 23 * * *', values: { expression: '30 23 * * *' } },
] satisfies Array<{ key: string; label: string; values: Record<string, string> }>

const jsonPathPresets = [
  { key: 'jsonpath-all-ids', label: '$.items[*].sku', values: { path: '$.items[*].sku' } },
  { key: 'jsonpath-first-role', label: '$.user.roles[0]', values: { path: '$.user.roles[0]' } },
  { key: 'jsonpath-total', label: '$.meta.total', values: { path: '$.meta.total' } },
] satisfies Array<{ key: string; label: string; values: Record<string, string> }>

const sampleImageDataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+X1cAAAAASUVORK5CYII='
const singleJsonToolNames = new Set(['json_format', 'json_minify', 'json_validate', 'jsonpath_query', 'json_to_xml', 'json_to_yaml', 'json_to_csv'])
const cronToolNames = new Set(['cron_generate', 'cron_parse', 'cron_next_runs', 'cron_validate'])

const applyFormValues = (values: Record<string, any>) => {
  toolForm.value = { ...toolForm.value, ...cloneValue(values) }
}

const normalizedJsonIndent = () => {
  const value = Number(toolForm.value.indent ?? 2)
  return Number.isFinite(value) ? Math.min(Math.max(value, 0), 8) : 2
}

const sortJsonKeys = (value: any): any => {
  if (Array.isArray(value)) return value.map(item => sortJsonKeys(item))
  if (!value || typeof value !== 'object') return value
  return Object.keys(value)
    .sort((left, right) => left.localeCompare(right))
    .reduce<Record<string, any>>((result, key) => {
      result[key] = sortJsonKeys(value[key])
      return result
    }, {})
}

const parseJsonFieldValue = (fieldName: string) => {
  const rawValue = String(toolForm.value[fieldName] ?? '').trim()
  if (!rawValue) throw new Error('Please enter JSON first.')
  return JSON.parse(rawValue)
}

const formatJsonField = (fieldName: string, options?: { minify?: boolean }) => {
  try {
    const parsed = parseJsonFieldValue(fieldName)
    const shouldSortKeys = Boolean(toolForm.value.sort_keys)
    const value = shouldSortKeys ? sortJsonKeys(parsed) : parsed
    toolForm.value[fieldName] = options?.minify
      ? JSON.stringify(value)
      : JSON.stringify(value, null, normalizedJsonIndent())
    Message.success(options?.minify ? 'JSON minified.' : 'JSON formatted.')
  } catch (error: any) {
    Message.warning(error?.message || 'Invalid JSON input.')
  }
}

const formatStructuredValue = (value: unknown) => {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}

const clearField = (fieldName: string) => {
  toolForm.value[fieldName] = ''
  const uploadInput = uploadInputs.get(fieldName)
  if (uploadInput) uploadInput.value = ''
}

const fillJsonSample = (fieldName: string, sampleText: string) => {
  toolForm.value[fieldName] = sampleText
}

const swapJsonDiffInputs = () => {
  const nextLeft = toolForm.value.right_text ?? ''
  const nextRight = toolForm.value.left_text ?? ''
  toolForm.value.left_text = nextLeft
  toolForm.value.right_text = nextRight
}

const stripDataUrlPrefix = (value: string) => value.replace(/^data:[^;]+;base64,/i, '').replace(/\s+/g, '')

const guessImageMimeType = (value: string) => {
  const base64 = stripDataUrlPrefix(value)
  if (!base64) return ''
  if (base64.startsWith('iVBOR')) return 'image/png'
  if (base64.startsWith('/9j/')) return 'image/jpeg'
  if (base64.startsWith('R0lGOD')) return 'image/gif'
  if (base64.startsWith('UklGR')) return 'image/webp'
  if (base64.startsWith('Qk')) return 'image/bmp'
  if (base64.startsWith('PHN2Zy')) return 'image/svg+xml'
  return ''
}

const resolveImagePreviewUrl = (value: unknown) => {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  if (!text) return ''
  if (text.startsWith('data:image/')) return text
  const mimeType = guessImageMimeType(text)
  if (!mimeType) return ''
  return `data:${mimeType};base64,${stripDataUrlPrefix(text)}`
}

const estimateBase64Bytes = (value: string) => {
  const base64 = stripDataUrlPrefix(value)
  if (!base64) return 0
  const padding = (base64.match(/=*$/)?.[0].length ?? 0)
  return Math.max(Math.floor(base64.length * 0.75) - padding, 0)
}

const sampleJsonForField = (toolName: string, fieldName: string) => {
  if (toolName === 'json_diff') return fieldName === 'left_text' ? sampleJsonDiffLeftText : sampleJsonDiffRightText
  if (toolName === 'json_to_csv') return sampleJsonArrayText
  return sampleJsonObjectText
}
const getToolField = (fieldName: string) => currentTool.value?.fields.find(field => field.name === fieldName) || null
const fieldLabel = (fieldName: string, fallback = fieldName) => getToolField(fieldName)?.label || fallback
const fieldPlaceholder = (fieldName: string, fallback = '') => getToolField(fieldName)?.placeholder || fallback
const fieldHelpText = (fieldName: string) => getToolField(fieldName)?.help_text || ''
const fieldOptions = (fieldName: string) => getToolField(fieldName)?.options || []
const fieldMin = (fieldName: string) => getToolField(fieldName)?.min
const fieldMax = (fieldName: string) => getToolField(fieldName)?.max
const fieldActionItemsByName = (fieldName: string) => {
  const field = getToolField(fieldName)
  return field ? fieldActionItems(field) : []
}

const analyseJsonInput = (value: unknown): JsonInputAnalysis => {
  const text = String(value ?? '')
  const trimmed = text.trim()
  if (!trimmed) {
    return {
      status: 'empty',
      charCount: 0,
      lineCount: 0,
      summary: 'Empty',
      help: 'Paste or generate a JSON payload to continue.',
    }
  }

  try {
    const parsed = JSON.parse(trimmed)
    const summary = Array.isArray(parsed)
      ? `Array | ${parsed.length} items`
      : parsed && typeof parsed === 'object'
        ? `Object | ${Object.keys(parsed).length} keys`
        : `Primitive | ${typeof parsed}`
    return {
      status: 'valid',
      charCount: text.length,
      lineCount: text.split(/\r?\n/).length,
      summary,
      help: 'JSON is valid and ready for execution.',
    }
  } catch (error: any) {
    return {
      status: 'invalid',
      charCount: text.length,
      lineCount: text.split(/\r?\n/).length,
      summary: 'Invalid JSON',
      help: error?.message || 'JSON syntax error detected.',
    }
  }
}

const categoryCards = computed<CategoryCard[]>(() => {
  const keyword = toolKeyword.value.trim().toLowerCase()
  return catalog.value.categories.map(category => {
    const tools = category.tools.filter(tool => (selectedScenario.value === 'all' || tool.scenario === selectedScenario.value) && matchKeyword(tool, keyword))
    return { ...category, toolCount: tools.length, previewTools: tools.slice(0, 3), scenarioNames: Array.from(new Set(tools.map(tool => scenarioLabel(tool.scenario)))) }
  })
})

const visibleCategories = computed<VisibleCategory[]>(() => {
  const keyword = toolKeyword.value.trim().toLowerCase()
  return catalog.value.categories.map(category => ({ ...category, visibleTools: category.tools.filter(tool => (selectedScenario.value === 'all' || tool.scenario === selectedScenario.value) && matchKeyword(tool, keyword)) })).filter(category => category.visibleTools.length > 0)
})

const workspaceCategories = computed<VisibleCategory[]>(() => focusedCategory.value === 'all' ? visibleCategories.value : visibleCategories.value.filter(category => category.category === focusedCategory.value))
const workspaceToolTotal = computed(() => workspaceCategories.value.reduce((total, category) => total + category.visibleTools.length, 0))
const activeScenarioLabel = computed(() => selectedScenario.value === 'all' ? '全部场景' : scenarioLabel(selectedScenario.value))
const workspaceTitle = computed(() => focusedCategory.value === 'all' ? '工具工作台' : `${categoryName(focusedCategory.value)}工具工作台`)
const workspaceDescription = computed(() => {
  const scope = focusedCategory.value === 'all' ? '默认展示全部分类工具。' : `当前已聚焦到“${categoryName(focusedCategory.value)}”。`
  return `${scope} 点击工具卡片会立即打开执行面板。`
})
const referencePickerTitle = computed(() => referencePickerMode.value === 'api' ? '浏览 API 数据工厂引用' : '浏览 UI 数据工厂引用')
const topReferenceTags = computed(() => statistics.value.tag_stats.slice(0, 6).map(item => {
  const detail = tags.value.find(tag => tag.id === item.id)
  return {
    ...item,
    preview: detail?.latest_preview || detail?.description || '',
  }
}))
const referenceRecords = computed(() => {
  const uniqueRecords = new Map<number, DataFactoryRecord>()
  for (const record of [...recentRecords.value, ...records.value]) {
    if (!record.is_saved || uniqueRecords.has(record.id)) continue
    uniqueRecords.set(record.id, record)
  }
  return Array.from(uniqueRecords.values()).slice(0, 6)
})

const currentTool = computed<DataFactoryTool | null>(() => catalog.value.tools.find(item => item.name === currentToolName.value) || null)
const specializedLayoutKind = computed<'generic' | 'jsonpath' | 'json-diff' | 'text-diff' | 'cron-generate' | 'cron-expression' | 'image-base64'>(() => {
  switch (currentTool.value?.name) {
    case 'jsonpath_query':
      return 'jsonpath'
    case 'json_diff':
      return 'json-diff'
    case 'text_diff':
      return 'text-diff'
    case 'cron_generate':
      return 'cron-generate'
    case 'cron_parse':
    case 'cron_next_runs':
    case 'cron_validate':
      return 'cron-expression'
    case 'image_base64_convert':
      return 'image-base64'
    default:
      return 'generic'
  }
})
const jsonPathSyntaxExamples = [
  '$.items[*].sku',
  '$.user.roles[0]',
  '$.meta.total',
]
const toolHelperDescription = computed(() => {
  switch (currentTool.value?.name) {
    case 'json_format':
    case 'json_minify':
    case 'json_validate':
    case 'json_to_xml':
    case 'json_to_yaml':
    case 'json_to_csv':
      return 'Use a sample payload, format the current JSON, or quickly clear the editor.'
    case 'jsonpath_query':
      return 'Fill a demo JSON document and apply common JSONPath expressions with one click.'
    case 'json_diff':
      return 'Load a ready-to-compare pair and switch the left/right JSON quickly.'
    case 'text_diff':
      return 'Load a sample pair, swap the two texts, or clear fields before comparing.'
    case 'regex_test':
      return 'Apply a ready-made pattern and sample text, then inspect matches and capture groups.'
    case 'cron_generate':
      return 'Apply common schedules directly to the five cron fields.'
    case 'cron_parse':
    case 'cron_next_runs':
    case 'cron_validate':
      return 'Try common expressions before editing the cron string manually.'
    case 'generate_qrcode':
      return 'Start from a URL or note template, then adjust size and border as needed.'
    case 'generate_barcode':
      return 'Fill a sample code and switch barcode styles faster.'
    case 'image_base64_convert':
      return 'Switch between image and Base64 mode, then upload, paste, or preview the current payload.'
    default:
      return ''
  }
})
const toolHelperPresets = computed<ToolPreset[]>(() => {
  switch (currentTool.value?.name) {
    case 'json_format':
      return [
        { key: 'json-format-sample', label: 'Sample JSON', values: { text: sampleJsonObjectText, sort_keys: false } },
        { key: 'json-format-current', label: 'Format Current', action: () => formatJsonField('text') },
        { key: 'json-format-sort', label: 'Enable Sort Keys', values: { sort_keys: true } },
      ]
    case 'json_minify':
      return [
        { key: 'json-minify-sample', label: 'Sample JSON', values: { text: sampleJsonObjectText } },
        { key: 'json-minify-current', label: 'Minify Current', action: () => formatJsonField('text', { minify: true }) },
      ]
    case 'json_validate':
      return [
        { key: 'json-validate-sample', label: 'Sample JSON', values: { text: sampleJsonObjectText } },
        { key: 'json-validate-format', label: 'Format Current', action: () => formatJsonField('text') },
      ]
    case 'jsonpath_query':
      return [
        { key: 'jsonpath-demo', label: 'Demo JSON + Path', values: { text: sampleJsonObjectText, path: '$.items[*].sku' } },
        ...jsonPathPresets,
      ]
    case 'json_diff':
      return [
        { key: 'json-diff-sample', label: 'Load Compare Pair', values: { left_text: sampleJsonDiffLeftText, right_text: sampleJsonDiffRightText } },
        { key: 'json-diff-swap', label: 'Swap Left / Right', action: swapJsonDiffInputs },
      ]
    case 'text_diff':
      return [
        { key: 'text-diff-sample', label: 'Load Compare Pair', values: { left_text: sampleTextDiffLeftText, right_text: sampleTextDiffRightText } },
        { key: 'text-diff-swap', label: 'Swap Left / Right', action: swapJsonDiffInputs },
      ]
    case 'regex_test':
      return [
        { key: 'regex-case-code', label: 'Case Code Pattern', values: { pattern: '^FT-[A-Z]+-\\d{3}$', text: sampleRegexCaseCodeText, flags: ['m'] } },
        { key: 'regex-email', label: 'Email Pattern', values: { pattern: '^[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}$', text: sampleRegexEmailText, flags: ['m'] } },
        { key: 'regex-clear', label: 'Clear Inputs', action: () => applyFormValues({ pattern: '', text: '', flags: [] }) },
      ]
    case 'json_to_xml':
      return [
        { key: 'json-xml-sample', label: 'Sample JSON', values: { text: sampleJsonObjectText, root_name: 'root' } },
        { key: 'json-xml-format', label: 'Format Current', action: () => formatJsonField('text') },
      ]
    case 'json_to_yaml':
      return [
        { key: 'json-yaml-sample', label: 'Sample JSON', values: { text: sampleJsonObjectText } },
        { key: 'json-yaml-format', label: 'Format Current', action: () => formatJsonField('text') },
      ]
    case 'json_to_csv':
      return [
        { key: 'json-csv-sample', label: 'Sample Rows', values: { text: sampleJsonArrayText } },
        { key: 'json-csv-format', label: 'Format Current', action: () => formatJsonField('text') },
      ]
    case 'cron_generate':
      return cronGeneratePresets.map(preset => ({ ...preset }))
    case 'cron_parse':
    case 'cron_next_runs':
    case 'cron_validate':
      return cronExpressionPresets.map(preset => ({
        ...preset,
        values: currentTool.value?.name === 'cron_next_runs'
          ? { ...preset.values, count: toolForm.value.count || 5, timezone: toolForm.value.timezone || 'Asia/Shanghai' }
          : preset.values,
      }))
    case 'generate_qrcode':
      return [
        { key: 'qrcode-url', label: 'Sample URL', values: { text: 'https://flytest.example.com/login', box_size: 8, border: 2 } },
        { key: 'qrcode-note', label: 'Sample Note', values: { text: 'FlyTest\\nUI automation\\nRun smoke suite' } },
      ]
    case 'generate_barcode':
      return [
        { key: 'barcode-order', label: 'Order Code', values: { text: 'FT202604060001', barcode_type: 'code128' } },
        { key: 'barcode-product', label: 'Product SKU', values: { text: 'SKU-FT-9001', barcode_type: 'code128' } },
      ]
    case 'image_base64_convert':
      return [
        { key: 'image-base64-image-mode', label: 'Image -> Base64', values: { mode: 'image_to_base64', image_data: '', include_prefix: true } },
        { key: 'image-base64-base64-mode', label: 'Base64 -> Image', values: { mode: 'base64_to_image', image_data: sampleImageDataUrl } },
        { key: 'image-base64-clear', label: 'Clear Input', action: () => clearField('image_data') },
      ]
    default:
      return []
  }
})
const imageInputModeLabel = computed(() => toolForm.value.mode === 'base64_to_image' ? 'Base64 Preview' : 'Image Preview')
const imageAssistantTip = computed(() => {
  if (currentTool.value?.name !== 'image_base64_convert') return ''
  return toolForm.value.mode === 'base64_to_image'
    ? 'Raw Base64 can be previewed automatically for PNG, JPEG, GIF, WebP, BMP, and SVG signatures.'
    : 'Upload an image or paste a data URL. The preview updates immediately before execution.'
})
const fieldPreviewImageUrl = (fieldName: string) => resolveImagePreviewUrl(toolForm.value[fieldName])
const describeImageInput = (fieldName: string) => {
  const value = toolForm.value[fieldName]
  if (typeof value !== 'string' || !value.trim()) return 'No image payload'
  const mimeType = value.startsWith('data:image/')
    ? value.slice(5, value.indexOf(';') > -1 ? value.indexOf(';') : undefined)
    : guessImageMimeType(value)
  const size = formatBytes(estimateBase64Bytes(value))
  return [mimeType || 'image/*', size].filter(Boolean).join(' | ')
}
const applyToolPreset = (preset: ToolPreset) => {
  if (preset.values) applyFormValues(preset.values)
  preset.action?.()
}
const fieldActionItems = (field: DataFactoryToolField): ToolFieldAction[] => {
  const toolName = currentTool.value?.name || ''
  const actions: ToolFieldAction[] = []
  if (field.name === 'text' && ['json_format', 'json_minify', 'json_validate', 'jsonpath_query', 'json_to_xml', 'json_to_yaml', 'json_to_csv'].includes(toolName)) {
    actions.push({ key: `${toolName}-${field.name}-sample`, label: 'Sample', run: () => fillJsonSample(field.name, sampleJsonForField(toolName, field.name)) })
    actions.push({ key: `${toolName}-${field.name}-format`, label: 'Format', run: () => formatJsonField(field.name) })
    if (toolName === 'json_minify') actions.push({ key: `${toolName}-${field.name}-minify`, label: 'Minify', run: () => formatJsonField(field.name, { minify: true }) })
    actions.push({ key: `${toolName}-${field.name}-clear`, label: 'Clear', run: () => clearField(field.name) })
  }
  if (toolName === 'json_diff' && ['left_text', 'right_text'].includes(field.name)) {
    actions.push({ key: `${field.name}-sample`, label: field.name === 'left_text' ? 'Sample A' : 'Sample B', run: () => fillJsonSample(field.name, sampleJsonForField(toolName, field.name)) })
    actions.push({ key: `${field.name}-format`, label: 'Format', run: () => formatJsonField(field.name) })
    actions.push({ key: `${field.name}-clear`, label: 'Clear', run: () => clearField(field.name) })
  }
  if (toolName === 'text_diff' && ['left_text', 'right_text'].includes(field.name)) {
    actions.push({ key: `${field.name}-sample`, label: field.name === 'left_text' ? 'Sample A' : 'Sample B', run: () => applyFormValues({ [field.name]: field.name === 'left_text' ? sampleTextDiffLeftText : sampleTextDiffRightText }) })
    actions.push({ key: `${field.name}-clear`, label: 'Clear', run: () => clearField(field.name) })
  }
  if (toolName === 'jsonpath_query' && field.name === 'path') {
    for (const preset of jsonPathPresets) actions.push({ key: preset.key, label: preset.label, run: () => applyFormValues(preset.values) })
    actions.push({ key: 'jsonpath-clear', label: 'Clear', run: () => clearField(field.name) })
  }
  if (toolName === 'regex_test' && field.name === 'pattern') {
    actions.push({ key: 'regex-pattern-id', label: 'Case ID', run: () => applyFormValues({ pattern: '^FT-[A-Z]+-\\d{3}$', flags: ['m'] }) })
    actions.push({ key: 'regex-pattern-email', label: 'Email', run: () => applyFormValues({ pattern: '^[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}$', flags: ['m'] }) })
    actions.push({ key: 'regex-pattern-clear', label: 'Clear', run: () => clearField(field.name) })
  }
  if (toolName === 'regex_test' && field.name === 'text') {
    actions.push({ key: 'regex-text-sample', label: 'Sample Text', run: () => applyFormValues({ text: sampleRegexCaseCodeText }) })
    actions.push({ key: 'regex-text-clear', label: 'Clear', run: () => clearField(field.name) })
  }
  if (['cron_parse', 'cron_next_runs', 'cron_validate'].includes(toolName) && field.name === 'expression') {
    for (const preset of cronExpressionPresets) actions.push({ key: preset.key, label: preset.label, run: () => applyFormValues(preset.values) })
    actions.push({ key: `${toolName}-clear`, label: 'Clear', run: () => clearField(field.name) })
  }
  if (['generate_qrcode', 'generate_barcode'].includes(toolName) && field.name === 'text') {
    actions.push({ key: `${toolName}-clear`, label: 'Clear', run: () => clearField(field.name) })
  }
  if (field.type === 'upload-base64') {
    if (toolName === 'image_base64_convert' && toolForm.value.mode === 'base64_to_image') {
      actions.push({ key: 'upload-base64-sample', label: 'Sample Base64', run: () => applyFormValues({ [field.name]: sampleImageDataUrl }) })
    }
    actions.push({ key: 'upload-base64-clear', label: 'Clear', run: () => clearField(field.name) })
  }
  return actions
}
const currentJsonAnalysis = computed<JsonInputAnalysis | null>(() => {
  const toolName = currentTool.value?.name || ''
  if (!singleJsonToolNames.has(toolName)) return null
  return analyseJsonInput(toolForm.value.text)
})
const jsonDiffLeftAnalysis = computed(() => currentTool.value?.name === 'json_diff' ? analyseJsonInput(toolForm.value.left_text) : null)
const jsonDiffRightAnalysis = computed(() => currentTool.value?.name === 'json_diff' ? analyseJsonInput(toolForm.value.right_text) : null)
const activeUploadFieldName = computed(() => currentTool.value?.fields.find(field => field.type === 'upload-base64')?.name || '')
const activeUploadPreviewUrl = computed(() => activeUploadFieldName.value ? fieldPreviewImageUrl(activeUploadFieldName.value) : '')
const activeUploadDescription = computed(() => activeUploadFieldName.value ? describeImageInput(activeUploadFieldName.value) : 'No image payload')
const cronExpressionPreview = computed(() => {
  const toolName = currentTool.value?.name || ''
  if (!cronToolNames.has(toolName)) return ''
  if (toolName === 'cron_generate') {
    return [
      String(toolForm.value.minute || '*').trim() || '*',
      String(toolForm.value.hour || '*').trim() || '*',
      String(toolForm.value.day || '*').trim() || '*',
      String(toolForm.value.month || '*').trim() || '*',
      String(toolForm.value.weekday || '*').trim() || '*',
    ].join(' ')
  }
  return String(toolForm.value.expression || '').trim()
})
const cronSegmentCount = computed(() => cronExpressionPreview.value ? cronExpressionPreview.value.split(/\s+/).filter(Boolean).length : 0)
const cronPreviewStatus = computed(() => {
  if (!cronExpressionPreview.value) return { text: 'Waiting for input', tone: 'warning' as const, help: 'Fill the cron fields or apply a preset.' }
  if (cronSegmentCount.value === 5) return { text: '5 fields ready', tone: 'success' as const, help: 'Expression shape looks correct for a standard cron entry.' }
  return { text: `${cronSegmentCount.value} fields`, tone: 'warning' as const, help: 'Cron expression should contain exactly 5 space-separated fields.' }
})
const toolWorkbenchCards = computed<ToolWorkbenchCard[]>(() => {
  const toolName = currentTool.value?.name || ''
  if (!toolName) return []

  if (currentJsonAnalysis.value) {
    return [
      { key: 'json-status', label: 'JSON status', value: currentJsonAnalysis.value.summary, help: currentJsonAnalysis.value.help, tone: currentJsonAnalysis.value.status === 'valid' ? 'success' : currentJsonAnalysis.value.status === 'invalid' ? 'warning' : 'default' },
      { key: 'json-chars', label: 'Characters', value: String(currentJsonAnalysis.value.charCount), help: 'Current input length in characters.' },
      { key: 'json-lines', label: 'Lines', value: String(currentJsonAnalysis.value.lineCount), help: 'Useful when reviewing formatted payloads.' },
    ]
  }

  if (toolName === 'json_diff' && jsonDiffLeftAnalysis.value && jsonDiffRightAnalysis.value) {
    const ready = jsonDiffLeftAnalysis.value.status === 'valid' && jsonDiffRightAnalysis.value.status === 'valid'
    return [
      { key: 'json-diff-left', label: 'Left JSON', value: jsonDiffLeftAnalysis.value.summary, help: jsonDiffLeftAnalysis.value.help, tone: jsonDiffLeftAnalysis.value.status === 'valid' ? 'success' : jsonDiffLeftAnalysis.value.status === 'invalid' ? 'warning' : 'default' },
      { key: 'json-diff-right', label: 'Right JSON', value: jsonDiffRightAnalysis.value.summary, help: jsonDiffRightAnalysis.value.help, tone: jsonDiffRightAnalysis.value.status === 'valid' ? 'success' : jsonDiffRightAnalysis.value.status === 'invalid' ? 'warning' : 'default' },
      { key: 'json-diff-ready', label: 'Compare status', value: ready ? 'Ready to compare' : 'Need valid pair', help: ready ? 'Both inputs are valid JSON.' : 'Load samples or format both sides before running.', tone: ready ? 'success' : 'warning' },
    ]
  }

  if (toolName === 'text_diff') {
    const leftText = String(toolForm.value.left_text || '')
    const rightText = String(toolForm.value.right_text || '')
    const leftLines = leftText ? leftText.split(/\r?\n/).length : 0
    const rightLines = rightText ? rightText.split(/\r?\n/).length : 0
    const ready = Boolean(leftText.trim() && rightText.trim())
    return [
      { key: 'text-diff-left', label: 'Text A', value: `${leftLines} lines`, help: leftText ? `${leftText.length} characters in the left document.` : 'Paste the first text block to compare.', tone: leftText ? 'success' : 'default' },
      { key: 'text-diff-right', label: 'Text B', value: `${rightLines} lines`, help: rightText ? `${rightText.length} characters in the right document.` : 'Paste the second text block to compare.', tone: rightText ? 'success' : 'default' },
      { key: 'text-diff-ready', label: 'Compare status', value: ready ? 'Ready to compare' : 'Need both texts', help: ready ? 'Both text areas contain content and can be compared now.' : 'Fill both sides or apply the sample pair first.', tone: ready ? 'success' : 'warning' },
    ]
  }

  if (toolName === 'regex_test') {
    const pattern = String(toolForm.value.pattern || '')
    const text = String(toolForm.value.text || '')
    const flags = Array.isArray(toolForm.value.flags) ? toolForm.value.flags.join('') : ''
    let regexTone: ToolWorkbenchCard['tone'] = 'default'
    let regexValue = pattern ? 'Pattern ready' : 'Waiting for pattern'
    let regexHelp = pattern ? 'Current expression can be compiled in the browser preview.' : 'Enter a regex pattern or apply a preset.'

    if (pattern) {
      try {
        new RegExp(pattern, flags)
        regexTone = 'success'
      } catch (error: any) {
        regexTone = 'warning'
        regexValue = 'Pattern error'
        regexHelp = error?.message || 'Regex syntax error detected.'
      }
    }

    return [
      { key: 'regex-status', label: 'Regex status', value: regexValue, help: regexHelp, tone: regexTone },
      { key: 'regex-input', label: 'Input size', value: `${text ? text.split(/\r?\n/).length : 0} lines`, help: text ? `${text.length} characters ready for matching.` : 'Paste the text that should be tested.' },
      { key: 'regex-flags', label: 'Flags', value: flags || 'None', help: 'Supported flags match the backend executor: i, m, and s.' },
    ]
  }

  if (cronToolNames.has(toolName)) {
    return [
      { key: 'cron-preview', label: 'Expression', value: cronExpressionPreview.value || 'Not set', help: cronPreviewStatus.value.help, tone: cronPreviewStatus.value.tone },
      { key: 'cron-fields', label: 'Field count', value: String(cronSegmentCount.value || 0), help: 'Standard cron expressions here use 5 fields.' },
      { key: 'cron-mode', label: 'Tool mode', value: toolName === 'cron_generate' ? 'Generator' : 'Expression inspector', help: toolName === 'cron_generate' ? 'Build the expression from separate cron fields.' : 'Parse, validate, or inspect an existing expression.' },
    ]
  }

  if (toolName === 'image_base64_convert') {
    return [
      { key: 'image-mode', label: 'Mode', value: toolForm.value.mode === 'base64_to_image' ? 'Base64 -> Image' : 'Image -> Base64', help: 'Switch mode from the shortcuts above when needed.' },
      { key: 'image-preview', label: 'Preview', value: activeUploadPreviewUrl.value ? 'Available' : 'Waiting for input', help: activeUploadPreviewUrl.value ? activeUploadDescription.value : 'Paste an image data URL or upload a file to preview it.', tone: activeUploadPreviewUrl.value ? 'success' : 'default' },
      { key: 'image-prefix', label: 'Data URL prefix', value: toolForm.value.include_prefix === false ? 'Disabled' : 'Enabled', help: 'When enabled, generated Base64 keeps the `data:image/...;base64,` prefix.' },
    ]
  }

  if (toolName === 'generate_qrcode') {
    return [
      { key: 'qrcode-content', label: 'Content size', value: `${String(toolForm.value.text || '').length} chars`, help: 'Longer content creates denser QR matrices.' },
      { key: 'qrcode-size', label: 'Box size', value: String(toolForm.value.box_size || 8), help: 'Higher values create larger QR code images.' },
      { key: 'qrcode-border', label: 'Border', value: String(toolForm.value.border || 2), help: 'Quiet zone around the QR code for scanning reliability.' },
    ]
  }

  if (toolName === 'generate_barcode') {
    return [
      { key: 'barcode-content', label: 'Content size', value: `${String(toolForm.value.text || '').length} chars`, help: 'Barcode payload length affects generated width.' },
      { key: 'barcode-type', label: 'Barcode type', value: String(toolForm.value.barcode_type || 'code128').toUpperCase(), help: 'Switch format depending on the code standard you need.' },
    ]
  }

  return []
})
const executionOutput = computed(() => lastExecution.value?.record?.output_data || lastExecution.value?.output_data || null)
const activeResultInput = computed<Record<string, any>>(() => (lastExecution.value?.record?.input_data as Record<string, any> | undefined) || toolForm.value || {})
const resultToolName = computed(() => lastExecution.value?.tool?.name || currentTool.value?.name || '')
const resultKind = computed(() => lastExecution.value?.tool?.result_kind || currentTool.value?.result_kind || 'json')
const resultValue = computed(() => executionOutput.value?.result ?? null)
const resultSpecialLayout = computed<ResultSpecialLayout>(() => {
  switch (resultToolName.value) {
    case 'json_validate':
      return 'json-validate'
    case 'jsonpath_query':
      return 'jsonpath'
    case 'json_diff':
      return 'json-diff'
    case 'text_diff':
      return 'text-diff'
    case 'regex_test':
      return 'regex-test'
    case 'json_to_xml':
    case 'json_to_yaml':
      return 'json-text'
    case 'json_to_csv':
      return 'json-to-csv'
    case 'cron_generate':
      return 'cron-generate'
    case 'cron_parse':
      return 'cron-parse'
    case 'cron_next_runs':
      return 'cron-next-runs'
    case 'cron_validate':
      return 'cron-validate'
    case 'image_base64_convert':
      return 'image-base64'
    case 'aes_encrypt':
      return 'aes-encrypt'
    default:
      return 'generic'
  }
})
const jsonValidateResult = computed(() => {
  if (resultSpecialLayout.value !== 'json-validate' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    valid: Boolean(resultValue.value.valid),
    type: String(resultValue.value.type || ''),
    message: String(resultValue.value.message || ''),
    line: Number(resultValue.value.line || 0),
    column: Number(resultValue.value.column || 0),
  }
})
const jsonPathResult = computed(() => {
  if (resultSpecialLayout.value !== 'jsonpath' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    path: String(resultValue.value.path || ''),
    matches: Array.isArray(resultValue.value.matches) ? resultValue.value.matches : [],
    count: Number(resultValue.value.count || 0),
  }
})
const jsonDiffResult = computed(() => {
  if (resultSpecialLayout.value !== 'json-diff' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    different: Boolean(resultValue.value.different),
    count: Number(resultValue.value.count || 0),
    diffs: Array.isArray(resultValue.value.diffs) ? resultValue.value.diffs : [],
  }
})
const textDiffResult = computed(() => {
  if (resultSpecialLayout.value !== 'text-diff' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    similarity: Number(resultValue.value.similarity || 0),
    same: Boolean(resultValue.value.same),
    diffLines: Array.isArray(resultValue.value.diff_lines) ? resultValue.value.diff_lines.map(item => String(item)) : [],
    leftLineCount: Number(resultValue.value.left_line_count || 0),
    rightLineCount: Number(resultValue.value.right_line_count || 0),
  }
})
const regexTestResult = computed(() => {
  if (resultSpecialLayout.value !== 'regex-test' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    matched: Boolean(resultValue.value.matched),
    count: Number(resultValue.value.count || 0),
    matches: Array.isArray(resultValue.value.matches)
      ? resultValue.value.matches.map((match, index) => ({
          key: `regex-match-${index}`,
          match: String(match?.match || ''),
          start: Number(match?.start || 0),
          end: Number(match?.end || 0),
          groups: Array.isArray(match?.groups) ? match.groups : [],
          groupDict: match?.group_dict && typeof match.group_dict === 'object' ? match.group_dict : {},
        }))
      : [],
  }
})
const jsonTextResult = computed(() => resultSpecialLayout.value === 'json-text' && typeof resultValue.value === 'string' ? resultValue.value : '')
const jsonTextResultMetrics = computed(() => ({
  lineCount: jsonTextResult.value ? jsonTextResult.value.split(/\r?\n/).length : 0,
  charCount: jsonTextResult.value.length,
}))
const jsonTextResultFormat = computed(() => resultToolName.value === 'json_to_xml' ? 'XML' : resultToolName.value === 'json_to_yaml' ? 'YAML' : 'Text')
const csvResultText = computed(() => resultSpecialLayout.value === 'json-to-csv' && typeof resultValue.value === 'string' ? resultValue.value : '')
const csvColumns = computed(() => Array.isArray(executionOutput.value?.metadata?.columns) ? executionOutput.value.metadata.columns.map((item: unknown) => String(item)) : [])
const csvRowCount = computed(() => {
  const lines = csvResultText.value.trim().split(/\r?\n/).filter(Boolean)
  return lines.length ? Math.max(lines.length - 1, 0) : 0
})
const cronParseResult = computed(() => {
  if (resultSpecialLayout.value !== 'cron-parse' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    expression: String(resultValue.value.expression || ''),
    minute: String(resultValue.value.minute || ''),
    hour: String(resultValue.value.hour || ''),
    day: String(resultValue.value.day || ''),
    month: String(resultValue.value.month || ''),
    weekday: String(resultValue.value.weekday || ''),
  }
})
const cronGeneratedExpression = computed(() => {
  if (resultSpecialLayout.value !== 'cron-generate') return ''
  return typeof resultValue.value === 'string' ? resultValue.value : ''
})
const cronNextRunsResult = computed(() => {
  if (resultSpecialLayout.value !== 'cron-next-runs' || !Array.isArray(resultValue.value)) return []
  return resultValue.value.map(item => String(item))
})
const cronValidateResult = computed(() => {
  if (resultSpecialLayout.value !== 'cron-validate' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    valid: Boolean(resultValue.value.valid),
    message: String(resultValue.value.message || ''),
  }
})
const imageBase64ResultText = computed(() => resultSpecialLayout.value === 'image-base64' && typeof resultValue.value === 'string' ? resultValue.value : '')
const imageBase64ResultObject = computed(() => {
  if (resultSpecialLayout.value !== 'image-base64' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    data_url: String(resultValue.value.data_url || ''),
    mime_type: String(resultValue.value.mime_type || ''),
    size: Number(resultValue.value.size || 0),
  }
})
const imageBase64ResultPreviewUrl = computed(() => {
  if (imageBase64ResultObject.value?.data_url) return imageBase64ResultObject.value.data_url
  if (imageBase64ResultText.value.startsWith('data:image/')) return imageBase64ResultText.value
  return ''
})
const aesEncryptResult = computed(() => {
  if (resultSpecialLayout.value !== 'aes-encrypt' || !resultValue.value || typeof resultValue.value !== 'object' || Array.isArray(resultValue.value)) return null
  return {
    cipherText: String(resultValue.value.cipher_text || ''),
    iv: String(resultValue.value.iv || ''),
    mode: String(resultValue.value.mode || ''),
  }
})
const resultImageUrl = computed(() => resultKind.value !== 'image' ? '' : typeof resultValue.value === 'string' ? resultValue.value : String(resultValue.value?.data_url || ''))
const jsonTreeSource = computed(() => resultKind.value !== 'json-tree' ? null : resultValue.value && typeof resultValue.value === 'object' && 'parsed' in resultValue.value ? resultValue.value.parsed : resultValue.value)
const formattedResult = computed(() => resultValue.value == null ? '' : resultKind.value === 'json-tree' && resultValue.value && typeof resultValue.value === 'object' && 'text' in resultValue.value ? String(resultValue.value.text || '') : typeof resultValue.value === 'string' ? resultValue.value : JSON.stringify(resultValue.value, null, 2))
const canCopyResult = computed(() => resultValue.value != null)
const canDownloadResult = computed(() => resultKind.value !== 'image' && Boolean(formattedResult.value))
const recentRecords = computed(() => statistics.value.recent_records || [])
const jsonTreeData = computed<JsonTreeNode[]>(() => jsonTreeSource.value == null ? [] : [buildJsonTreeNode('root', jsonTreeSource.value, 'root')])
const jsonExpandedKeys = ref<string[]>([])
const allJsonNodeKeys = computed(() => collectJsonNodeKeys(jsonTreeData.value))
const previewImageUrl = computed(() => {
  if (resultKind.value === 'image') return ''
  if (typeof resultValue.value !== 'string') return ''
  return resultValue.value.startsWith('data:image/') ? resultValue.value : ''
})
const resultMetadataEntries = computed(() => {
  const metadata = executionOutput.value?.metadata
  if (!metadata || typeof metadata !== 'object') return []
  const hiddenKeys = new Set<string>()
  if (resultSpecialLayout.value === 'cron-next-runs') hiddenKeys.add('timezone')
  if (resultSpecialLayout.value === 'json-to-csv') hiddenKeys.add('columns')
  return Object.entries(metadata)
    .filter(([label, value]) => value !== '' && value !== null && value !== undefined && !hiddenKeys.has(label))
    .map(([label, value]) => ({
      label,
      value: typeof value === 'string' ? value : JSON.stringify(value),
    }))
})
const imageResultMeta = computed(() => {
  if (resultKind.value !== 'image' || !resultValue.value || typeof resultValue.value !== 'object') return []
  return [
    { label: '类型', value: String(resultValue.value.mime_type || 'image/png') },
    { label: '大小', value: formatBytes(Number(resultValue.value.size || 0)) },
  ].filter(item => item.value && item.value !== '0 B')
})

const categoryBreakdown = computed(() => {
  const maxTotal = Math.max(...statistics.value.category_stats.map(item => item.total), 0)
  return catalog.value.categories.map(category => {
    const total = statistics.value.category_stats.find(item => item.tool_category === category.category)?.total ?? 0
    return { key: category.category, name: category.name, total, percent: maxTotal > 0 ? Math.max((total / maxTotal) * 100, total > 0 ? 8 : 0) : 0 }
  })
})

const scenarioBreakdown = computed(() => {
  const maxTotal = Math.max(...statistics.value.scenario_stats.map(item => item.total), 0)
  return catalog.value.scenarios.map(scenario => {
    const total = statistics.value.scenario_stats.find(item => item.tool_scenario === scenario.scenario)?.total ?? 0
    return { key: scenario.scenario, name: scenario.name, total, percent: maxTotal > 0 ? Math.max((total / maxTotal) * 100, total > 0 ? 8 : 0) : 0 }
  })
})

const buildJsonTreeNode = (label: string, value: any, path: string): JsonTreeNode => Array.isArray(value) ? { key: path, title: `${label}: [${value.length}]`, children: value.map((item, index) => buildJsonTreeNode(`[${index}]`, item, `${path}.${index}`)) } : value && typeof value === 'object' ? { key: path, title: `${label}: {${Object.keys(value).length}}`, children: Object.entries(value).map(([key, item]) => buildJsonTreeNode(key, item, `${path}.${key}`)) } : { key: path, title: `${label}: ${String(value)}` }
const buildFallbackTool = (record: DataFactoryRecord): DataFactoryTool => ({ name: record.tool_name, display_name: record.tool_display_name, description: `${record.category_display} / ${record.scenario_display}`, category: record.tool_category, scenario: record.tool_scenario, icon: '', result_kind: 'json', fields: [] })
const isFullWidthField = (type: DataFactoryFieldType) => ['textarea', 'json', 'upload-base64'].includes(type)
const collectJsonNodeKeys = (nodes: JsonTreeNode[]) => nodes.flatMap(node => [String(node.key), ...(node.children ? collectJsonNodeKeys(node.children) : [])])
const formatBytes = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size >= 10 || index === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[index]}`
}

const buildToolFormState = (tool: DataFactoryTool | null, inputData?: Record<string, any> | null) => {
  const nextForm: Record<string, any> = {}
  for (const field of tool?.fields || []) {
    if (field.type === 'multi-select') nextForm[field.name] = Array.isArray(field.default) ? [...field.default] : []
    else if (field.type === 'switch') nextForm[field.name] = Boolean(field.default)
    else if (field.type === 'json') nextForm[field.name] = typeof field.default === 'string' ? field.default : JSON.stringify(field.default ?? {}, null, 2)
    else if (field.type === 'number') nextForm[field.name] = field.default ?? field.min ?? 0
    else nextForm[field.name] = field.default ?? ''
  }
  for (const field of tool?.fields || []) {
    if (!inputData || !(field.name in inputData)) continue
    const value = cloneValue(inputData[field.name])
    nextForm[field.name] = field.type === 'json' && typeof value !== 'string' ? JSON.stringify(value ?? {}, null, 2) : value
  }
  return nextForm
}

const resetProjectScopedState = () => {
  tags.value = []
  statistics.value = emptyStatistics()
  records.value = []
  lastExecution.value = null
  selectedTagIds.value = []
  tagNamesText.value = ''
  saveRecord.value = true
  recordPagination.total = 0
  recordPagination.current = 1
}

const resetToolForm = (tool: DataFactoryTool | null, inputData?: Record<string, any> | null) => {
  toolForm.value = buildToolFormState(tool, inputData)
}

const scrollToWorkspace = async () => {
  await nextTick()
  toolWorkspaceSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const applyScenarioFilter = async (scenario: ScenarioFilter) => {
  selectedScenario.value = scenario
  focusedCategory.value = 'all'
  viewMode.value = 'category'
  await scrollToWorkspace()
}

const focusCategorySection = async (category: DataFactoryCategoryKey) => {
  const keyword = toolKeyword.value.trim().toLowerCase()
  const hasVisible = catalog.value.categories.find(item => item.category === category)?.tools.some(tool => (selectedScenario.value === 'all' || tool.scenario === selectedScenario.value) && matchKeyword(tool, keyword))
  if (!hasVisible) selectedScenario.value = 'all'
  viewMode.value = 'category'
  focusedCategory.value = category
  await scrollToWorkspace()
}

const clearCategoryFocus = async () => {
  focusedCategory.value = 'all'
  await scrollToWorkspace()
}

const openReferenceBrowser = (mode: DataFactoryReferenceMode) => {
  if (!projectReady.value) {
    Message.warning('请先选择项目')
    return
  }
  referencePickerMode.value = mode
  referencePickerVisible.value = true
}

const openToolDialog = (tool: DataFactoryTool, options?: { inputData?: Record<string, any> | null; execution?: DataFactoryExecuteResult | null; tagIds?: number[]; saveRecord?: boolean }) => {
  currentToolName.value = tool.name
  lastExecution.value = options?.execution ?? null
  selectedTagIds.value = options?.tagIds ? [...options.tagIds] : []
  tagNamesText.value = ''
  saveRecord.value = options?.saveRecord ?? true
  resetToolForm(tool, options?.inputData)
  toolDialogVisible.value = true
}

const buildPayloadValue = (field: DataFactoryToolField) => {
  const rawValue = toolForm.value[field.name]
  if (field.required && (rawValue == null || rawValue === '' || (Array.isArray(rawValue) && !rawValue.length))) throw new Error(`请填写 ${field.label}`)
  return field.type === 'json' && typeof rawValue === 'string' ? (rawValue.trim() ? JSON.parse(rawValue) : field.default ?? {}) : rawValue
}

const loadCatalog = async () => { catalog.value = extractDataFactoryData<DataFactoryCatalog>(await dataFactoryApi.getCatalog()) }
const loadTags = async () => { if (!projectId.value) return; tags.value = extractDataFactoryData<any>(await dataFactoryApi.getTags({ project: projectId.value, page_size: 200 }))?.results ?? [] }
const loadStatistics = async () => { if (!projectId.value) return; statistics.value = extractDataFactoryData<DataFactoryStatistics>(await dataFactoryApi.getStatistics(projectId.value)) }

const loadRecords = async () => {
  if (!projectId.value) return
  loadingRecords.value = true
  try {
    const data = extractDataFactoryData<any>(await dataFactoryApi.getRecords({ project: projectId.value, page: recordPagination.current, page_size: recordPagination.pageSize, search: recordFilters.search || undefined, tool_category: recordFilters.category === 'all' ? undefined : recordFilters.category, tool_scenario: recordFilters.scenario === 'all' ? undefined : recordFilters.scenario, is_saved: recordFilters.saved === 'all' ? undefined : recordFilters.saved === 'saved' }))
    records.value = data?.results ?? []
    recordPagination.total = data?.count ?? 0
  } catch (error: any) {
    Message.error(normalizeErrorMessage(error, '加载使用记录失败'))
  } finally {
    loadingRecords.value = false
  }
}

const refreshAll = async () => {
  try {
    await loadCatalog()
    if (!projectId.value) return resetProjectScopedState()
    await Promise.all([loadTags(), loadStatistics(), loadRecords()])
  } catch (error: any) {
    Message.error(normalizeErrorMessage(error, '加载数据工厂失败'))
  }
}

const executeToolRun = async () => {
  if (!projectReady.value) return Message.warning('请先选择项目后再运行工具')
  if (!currentTool.value) return
  executing.value = true
  try {
    lastExecution.value = extractDataFactoryData<DataFactoryExecuteResult>(await dataFactoryApi.execute({ project: projectId.value!, tool_name: currentTool.value.name, input_data: Object.fromEntries(currentTool.value.fields.map(field => [field.name, buildPayloadValue(field)])), save_record: saveRecord.value, tag_ids: selectedTagIds.value, tag_names: tagNamesText.value.split(/[,\n，]+/).map(item => item.trim()).filter(Boolean) }))
    Message.success('工具运行成功')
    await Promise.all([loadTags(), loadStatistics(), loadRecords()])
  } catch (error: any) {
    Message.error(normalizeErrorMessage(error, '工具运行失败'))
  } finally {
    executing.value = false
  }
}

const searchRecords = () => { if (projectReady.value) { recordPagination.current = 1; void loadRecords() } }
const handleRecordPageChange = (page: number) => { if (projectReady.value) { recordPagination.current = page; void loadRecords() } }
const handleRecordPageSizeChange = (pageSize: number) => { if (projectReady.value) { recordPagination.pageSize = pageSize; recordPagination.current = 1; void loadRecords() } }

const showRecordResult = async (record: DataFactoryRecord) => {
  if (!projectReady.value) return
  try {
    const detail = extractDataFactoryData<DataFactoryRecord>(await dataFactoryApi.getRecord(record.id))
    const tool = catalog.value.tools.find(item => item.name === detail.tool_name) || buildFallbackTool(detail)
    openToolDialog(tool, { inputData: detail.input_data, execution: { tool, output_data: detail.output_data, saved: detail.is_saved, record: detail }, tagIds: detail.tags.map(item => item.id), saveRecord: detail.is_saved })
  } catch (error: any) {
    Message.error(normalizeErrorMessage(error, '加载记录详情失败'))
  }
}

const deleteRecord = async (id: number) => {
  if (!projectReady.value) return
  try {
    await dataFactoryApi.deleteRecord(id)
    Message.success('记录已删除')
    await Promise.all([loadRecords(), loadStatistics(), loadTags()])
  } catch (error: any) {
    Message.error(normalizeErrorMessage(error, '删除记录失败'))
  }
}

const copyText = async (text: string, message = '已复制') => {
  if (!text) {
    Message.warning('暂无可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    Message.success(message)
  } catch (error) {
    Message.error('复制失败，请手动复制')
  }
}

const copyTagReference = (code: string, mode: DataFactoryReferenceMode) =>
  copyText(
    buildDataFactoryPlaceholder('tag', code, mode),
    `已复制 ${mode === 'api' ? 'API' : 'UI'} 标签引用`
  )

const handleReferenceSelect = (placeholder: string) =>
  copyText(placeholder, `已复制 ${referencePickerMode.value === 'api' ? 'API' : 'UI'} 引用`)

const copyResultContent = () => copyText(formattedResult.value, '已复制工具结果')

const downloadResultContent = () => {
  if (!formattedResult.value) {
    Message.warning('当前没有可下载的结果')
    return
  }
  const extension = resultKind.value === 'json-tree' || formattedResult.value.trim().startsWith('{') || formattedResult.value.trim().startsWith('[') ? 'json' : 'txt'
  const blob = new Blob([formattedResult.value], { type: extension === 'json' ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${currentTool.value?.name || 'data-factory-result'}.${extension}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
  Message.success('结果下载已开始')
}

const downloadResultImage = () => {
  if (!resultImageUrl.value) {
    Message.warning('当前没有可下载的图片结果')
    return
  }
  const link = document.createElement('a')
  link.href = resultImageUrl.value
  link.download = `${currentTool.value?.name || 'data-factory-result'}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  Message.success('图片下载已开始')
}

const expandAllJson = () => {
  jsonExpandedKeys.value = [...allJsonNodeKeys.value]
}

const collapseAllJson = () => {
  jsonExpandedKeys.value = jsonTreeData.value.length ? [String(jsonTreeData.value[0].key)] : []
}

const handleJsonExpand = (keys: Array<string | number>) => {
  jsonExpandedKeys.value = keys.map(key => String(key))
}

const registerUploadInput = (fieldName: string, element: HTMLInputElement | null) => {
  if (element) uploadInputs.set(fieldName, element)
  else uploadInputs.delete(fieldName)
}

const handleImagePicked = (fieldName: string, event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    toolForm.value[fieldName] = String(reader.result || '')
  }
  reader.readAsDataURL(file)
}

const triggerImagePicker = (fieldName: string) => uploadInputs.get(fieldName)?.click()
const handleTagsUpdated = () => { if (projectReady.value) void Promise.all([loadTags(), loadStatistics(), loadRecords()]) }

watch(() => projectId.value, () => void refreshAll(), { immediate: true })
watch(
  visibleCategories,
  categories => {
    if (focusedCategory.value !== 'all' && !categories.some(category => category.category === focusedCategory.value)) {
      focusedCategory.value = 'all'
    }
  },
  { immediate: true }
)
watch(
  jsonTreeData,
  nodes => {
    jsonExpandedKeys.value = collectJsonNodeKeys(nodes)
  },
  { immediate: true }
)
</script>

<style scoped>
.data-factory-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  box-sizing: border-box;
  overflow: visible;
}

.panel { border: 1px solid var(--color-border-2); border-radius: 22px; background: var(--color-bg-2); box-shadow: 0 12px 28px rgba(15,23,42,.05); padding: 18px; }
.hero { display: flex; justify-content: space-between; gap: 24px; background: radial-gradient(circle at top right, rgba(var(--primary-6),.1), transparent 28%), linear-gradient(135deg, var(--color-bg-2) 0%, var(--color-fill-1) 100%); }
.hero__eyebrow { font-size: 13px; letter-spacing: .16em; text-transform: uppercase; color: rgb(var(--primary-6)); font-weight: 700; }
.hero__title { margin: 6px 0 10px; font-size: 40px; line-height: 1; color: var(--color-text-1); }
.hero__desc { margin: 0; max-width: 860px; line-height: 1.8; color: var(--color-text-2); }
.hero__meta, .hero__actions, .pill-row, .overview-card__chips, .section-head { display: flex; flex-wrap: wrap; gap: 10px; }
.hero__meta { margin-top: 12px; }
.hero__meta span, .pill { padding: 6px 12px; border-radius: 999px; font-size: 12px; }
.hero__meta span, .pill.active, .is-primary { background: rgba(var(--primary-6),.08); color: rgb(var(--primary-6)); font-weight: 600; }
.hero__actions { flex-direction: column; align-items: flex-end; justify-content: space-between; }
.banner { display: grid; gap: 8px; border-style: dashed; }
.section-head { justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.section-title { font-size: 17px; font-weight: 700; color: var(--color-text-1); }
.section-desc, .overview-card__desc, .tool-card__desc, .recent__meta, .recent__preview, .record-tool span, .field-help { font-size: 12px; line-height: 1.7; color: var(--color-text-3); }
.tool-search { width: 320px; }
.overview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.overview-card, .scenario-card, .tool-card, .recent, .pill { border: 1px solid var(--color-border-2); background: var(--color-fill-1); cursor: pointer; transition: all .2s ease; }
.overview-card, .scenario-card { padding: 16px; border-radius: 18px; text-align: left; display: grid; gap: 10px; }
.overview-card:hover, .overview-card.active, .scenario-card:hover, .scenario-card.active, .tool-card:hover, .category-panel.active, .pill:hover, .pill.active { border-color: rgba(var(--primary-6),.32); background: rgba(var(--primary-6),.08); }
.overview-card__top, .metric__head, .category-panel__head, .category-panel__title, .tool-card, .tool-card__footer, .scenario-card__footer, .action-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.overview-card__icon, .scenario-card__icon, .category-panel__icon, .tool-card__icon { display: inline-flex; align-items: center; justify-content: center; background: rgba(var(--primary-6),.12); color: rgb(var(--primary-6)); }
.overview-card__icon, .scenario-card__icon, .category-panel__icon { width: 46px; height: 46px; border-radius: 16px; font-size: 24px; }
.tool-card__icon { width: 42px; height: 42px; border-radius: 14px; font-size: 20px; flex-shrink: 0; }
.overview-card__count { min-width: 42px; height: 42px; display: inline-flex; align-items: center; justify-content: center; border-radius: 14px; background: rgba(var(--primary-6),.12); color: rgb(var(--primary-6)); font-size: 18px; font-weight: 700; }
.overview-card__title, .scenario-card__title, .tool-card__title, .recent__title { font-weight: 700; color: var(--color-text-1); }
.overview-card__desc { min-height: 38px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.stat-card { display: flex; flex-direction: column; gap: 10px; }
.stat-card strong { font-size: 30px; color: var(--color-text-1); }
.insight-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.insight-grid--drawer { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.reference-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.workspace-panel { display: grid; gap: 16px; scroll-margin-top: 20px; }
.workspace-head { margin-bottom: 0; }
.workspace-actions, .workspace-summary { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.locked { opacity: .78; }
.metric-list, .recent-list, .category-list { display: grid; gap: 12px; }
.metric, .recent { padding: 14px; border-radius: 14px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.reference-list { display: grid; gap: 12px; }
.reference-item { padding: 14px; border-radius: 16px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); display: grid; gap: 10px; }
.reference-item--interactive { width: 100%; text-align: left; cursor: pointer; transition: all .2s ease; }
.reference-item--interactive:hover { border-color: rgba(var(--primary-6),.32); background: rgba(var(--primary-6),.08); }
.reference-item__head, .reference-item__actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.reference-item__title { font-weight: 700; color: var(--color-text-1); }
.reference-item__preview { font-size: 12px; line-height: 1.7; color: var(--color-text-3); word-break: break-word; }
.metric__track { height: 8px; border-radius: 999px; background: rgba(var(--primary-6),.08); overflow: hidden; }
.metric__bar { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, rgba(var(--primary-6),.55), rgb(var(--primary-6))); }
.metric__bar--soft { background: linear-gradient(90deg, rgba(54,127,255,.35), rgba(54,127,255,.9)); }
.recent { width: 100%; text-align: left; }
.recent__preview { margin-top: 8px; color: var(--color-text-2); word-break: break-word; }
.empty { padding: 14px; border-radius: 14px; border: 1px dashed var(--color-border-2); background: var(--color-fill-1); text-align: center; color: var(--color-text-3); font-size: 12px; line-height: 1.6; }
.scenario-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.scenario-card__footer { align-items: center; color: rgb(var(--primary-6)); font-weight: 700; }
.category-list { gap: 16px; }
.category-panel { scroll-margin-top: 20px; }
.category-panel__head { align-items: center; }
.tool-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.tool-card { padding: 16px; border-radius: 18px; text-align: left; }
.tool-card__body { flex: 1; display: grid; gap: 6px; min-width: 0; }
.tool-card__footer { align-items: center; color: var(--color-text-3); }
.tool-modal { display: flex; flex-direction: column; gap: 16px; }
.tool-modal__banner { display: flex; justify-content: space-between; gap: 16px; padding: 14px; border-radius: 16px; background: rgba(var(--primary-6),.06); }
.tool-modal__desc { font-size: 14px; color: var(--color-text-1); margin-bottom: 10px; }
.tool-modal__lock { padding: 10px 12px; border-radius: 14px; background: rgba(250,173,20,.1); color: #ad6800; font-size: 12px; }
.tool-modal__body { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); gap: 16px; }
.tool-pane { display: flex; flex-direction: column; gap: 14px; min-height: 520px; }
.tool-helper { display: grid; gap: 12px; padding: 14px; border-radius: 16px; border: 1px solid rgba(var(--primary-6), .14); background: rgba(var(--primary-6), .05); }
.tool-helper__intro, .tool-helper__actions, .field-actions, .input-preview__meta { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.tool-helper__actions, .field-actions { justify-content: flex-start; }
.tool-helper__head--legacy { display: none; }
.tool-workbench { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.tool-workbench__card, .tool-special-panel { display: grid; gap: 8px; padding: 14px; border-radius: 16px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.tool-workbench__card.is-success { border-color: rgba(var(--primary-6), .28); background: rgba(var(--primary-6), .08); }
.tool-workbench__card.is-warning { border-color: rgba(250, 173, 20, .35); background: rgba(250, 173, 20, .08); }
.tool-workbench__label, .tool-workbench__help { font-size: 12px; line-height: 1.6; color: var(--color-text-3); }
.tool-workbench__value { font-size: 16px; line-height: 1.4; color: var(--color-text-1); word-break: break-word; }
.tool-special-panel { background: linear-gradient(135deg, rgba(var(--primary-6), .05), var(--color-fill-1)); }
.tool-special-panel__head, .tool-special-panel__meta { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.tool-special-panel__code { margin: 0; padding: 14px; border-radius: 14px; background: var(--color-bg-2); border: 1px solid var(--color-border-2); font-size: 13px; line-height: 1.7; color: var(--color-text-1); white-space: pre-wrap; word-break: break-word; }
.special-form { display: grid; gap: 12px; }
.special-form--two-columns,
.special-form--compare,
.special-form__inline-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.special-form__panel { display: grid; gap: 10px; padding: 14px; border-radius: 16px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.special-form__panel--wide { min-width: 0; }
.special-form__label-row,
.special-form__meta-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.special-form__note { display: grid; gap: 8px; padding: 12px; border-radius: 14px; background: rgba(var(--primary-6), .05); border: 1px dashed rgba(var(--primary-6), .2); }
.special-form__note strong { font-size: 12px; color: var(--color-text-2); }
.special-form__note code { padding: 8px 10px; border-radius: 10px; background: var(--color-bg-2); border: 1px solid var(--color-border-2); font-size: 12px; color: rgb(var(--primary-6)); word-break: break-all; }
.special-form__cron-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.input-preview--static { padding: 0; border: none; background: transparent; }
.section-title--mini { font-size: 15px; }
.result-actions { display: flex; justify-content: flex-end; }
.sub-panel { display: grid; gap: 12px; margin-top: auto; }
.form-grid, .history-filters { display: grid; gap: 12px; }
.form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.field.full { grid-column: 1 / -1; }
.field label { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--color-text-1); }
.field-stack, .switch-row, .upload-wrap, .tree-result, .record-tool, .result-stack, .image-result, .result-meta, .input-preview { display: grid; gap: 10px; }
.switch-row { display: inline-flex; align-items: center; }
.hidden-input { display: none; }
.field-actions { margin-top: 2px; }
.input-preview { padding: 12px; border-radius: 14px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.input-preview__image { width: 100%; max-height: 220px; object-fit: contain; border-radius: 12px; background: var(--color-bg-2); border: 1px solid var(--color-border-2); }
.special-result, .special-result__list, .diff-list { display: grid; gap: 12px; }
.special-result__cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.special-result__cards--three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.special-result__cards--five { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.special-result__card, .special-result__list-item, .diff-item { display: grid; gap: 8px; padding: 14px; border-radius: 16px; border: 1px solid var(--color-border-2); background: var(--color-fill-1); }
.special-result__card.is-success { border-color: rgba(var(--primary-6), .28); background: rgba(var(--primary-6), .08); }
.special-result__card.is-warning, .diff-item { border-color: rgba(250, 173, 20, .28); background: rgba(250, 173, 20, .06); }
.special-result__label, .special-result__help, .diff-item__value span { font-size: 12px; line-height: 1.6; color: var(--color-text-3); }
.special-result__value { font-size: 16px; line-height: 1.45; color: var(--color-text-1); word-break: break-word; }
.special-result__list-head, .diff-item__head { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.diff-item__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.diff-item__value { display: grid; gap: 8px; min-width: 0; }
.result-inline-block { margin: 0; padding: 12px; border-radius: 12px; background: var(--color-bg-2); border: 1px solid var(--color-border-2); font-size: 12px; line-height: 1.65; color: var(--color-text-1); white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow: auto; }
.result-summary { padding: 12px 14px; border-radius: 14px; background: rgba(var(--primary-6),.08); color: var(--color-text-1); font-weight: 600; }
.result-block { margin: 0; padding: 14px; border-radius: 14px; background: var(--color-fill-1); font-size: 12px; line-height: 1.65; color: var(--color-text-1); white-space: pre-wrap; word-break: break-word; max-height: 460px; overflow: auto; }
.result-image { width: 100%; border-radius: 14px; border: 1px solid var(--color-border-2); }
.result-image--preview { max-height: 260px; object-fit: contain; background: var(--color-fill-1); }
.result-meta { grid-template-columns: repeat(auto-fit, minmax(120px, max-content)); }
.history-filters { grid-template-columns: minmax(220px, 1.3fr) repeat(3, minmax(160px, 1fr)); margin-bottom: 16px; }

@media (max-width: 1320px) {
  .insight-grid,
  .reference-grid,
  .tool-modal__body,
  .insight-grid--drawer { grid-template-columns: 1fr; }
}

@media (max-width: 1180px) {
  .stats-grid,
  .tool-workbench,
  .special-result__cards,
  .special-result__cards--three,
  .special-result__cards--five,
  .diff-item__grid,
  .special-form--two-columns,
  .special-form--compare,
  .special-form__inline-grid,
  .special-form__cron-grid,
  .history-filters,
  .form-grid { grid-template-columns: 1fr; }
  .scenario-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 1080px) {
  .data-factory-page { padding: 16px; }
  .hero, .section-head { flex-direction: column; }
  .hero__actions { align-items: stretch; }
  .tool-search { width: 100%; }
  .workspace-actions, .workspace-summary { align-items: stretch; }
  .overview-grid, .scenario-grid, .tool-grid { grid-template-columns: 1fr; }
}
</style>
