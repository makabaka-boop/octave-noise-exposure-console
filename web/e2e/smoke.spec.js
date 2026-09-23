// 仅一条主流程冒烟：
// 1) 填入样例 -> 提交 -> 看到总 LAeq / 超标结论 / 主导来源；
// 2) 改成非法输入 -> 校验失败，旧结论被清除；
// 3) 直连后端验证字段缺失整次 422（页面据此清结论的契约）。
import { test, expect, request as pwRequest } from '@playwright/test'

test('噪声暴露计算主流程 + 非法输入清除旧结论 + 422 契约', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: '填入联调样例' }).click()
  await page.getByTestId('submit-btn').click()

  await expect(page.getByTestId('result-panel')).toBeVisible()
  await expect(page.getByTestId('total-laeq')).toBeVisible()
  await expect(page.getByTestId('dominant')).toContainText('能量占比最高的来源')

  const verdictText = await page.getByTestId('verdict').innerText()
  expect(verdictText).toMatch(/总暴露 LAeq = \d+\.\d dB/)
  // 样例含 60s 高声级，能量合并后超过 85 dB 限值
  expect(verdictText).toContain('超标')

  // 把第一个时段 1000Hz 改成非法值 200（超出 0~140）=> 不发起计算，旧结论必须清除
  await page.getByLabel('时段1-1000Hz').fill('200')
  await page.getByTestId('submit-btn').click()
  await expect(page.getByTestId('errors')).toBeVisible()
  await expect(page.getByTestId('result-panel')).toHaveCount(0)

  // 后端契约：缺失频带整次 422（前端据此清结论）
  const api = await pwRequest.newContext({ baseURL: 'http://localhost:8000' })
  const bad = await api.post('/api/exposure', {
    data: {
      limit: 85,
      periods: [
        {
          duration: 60,
          levels: {
            63: 82, 125: 88, 250: 94, 500: 102,
            // 1000 Hz 缺失
            2000: 109, 4000: 106, 8000: 100,
          },
        },
      ],
    },
  })
  expect(bad.status()).toBe(422)
})
