import { expect, test } from '@playwright/test';

const password = 'Drishti@2026';

async function signIn(page, email) {
  await page.goto('/login');
  await page.locator('input[type="text"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
}

test('complaint routes, links across bureaus, notifies, and closes', async ({
  browser,
}) => {
  const complainantContext = await browser.newContext();
  const complainantPage = await complainantContext.newPage();
  await signIn(complainantPage, 'student@drishti.test');
  await expect(complainantPage).toHaveURL(/my-complaints/);
  await complainantPage.goto('/file-complaint');

  await complainantPage
    .getByPlaceholder('e.g. Apex Institute of Technology & Engineering')
    .fill('Apex Institute of Technology');
  await complainantPage
    .getByPlaceholder('e.g. Pune')
    .fill('Pune');
  await complainantPage.locator('select').nth(1).selectOption({
    label: 'Student Welfare',
  });
  await complainantPage
    .getByPlaceholder('Concise summary of the grievance issue')
    .fill('Ragging and unauthorized capitation fee at Apex Institute');
  await complainantPage
    .getByPlaceholder(
      'Detail the complete chronological account of events, names of officials/departments involved, dates, and AICTE regulations violated...',
    )
    .fill(
      'Apex Institute of Technology is demanding an unauthorized cash donation of Rs 350000 under the guise of developmental fees prior to issuing the admission confirmation slip. Students also report ragging and intimidation in the hostel.',
    );
  await complainantPage.getByRole('button', { name: /lodge grievance/i }).click();

  const receipt = complainantPage.getByText(/^DRI-\d{4}-\d{6}$/);
  await expect(receipt).toBeVisible({ timeout: 30_000 });
  const receiptId = await receipt.innerText();
  await expect(complainantPage.getByText('Student Cell', { exact: true })).toBeVisible();
  await expect(complainantPage.getByText('Assigned', { exact: true })).toBeVisible();

  const officerContext = await browser.newContext();
  const officerPage = await officerContext.newPage();
  await signIn(officerPage, 'official.sc@drishti.test');
  await expect(officerPage).toHaveURL(/official\/inbox/);
  const search = officerPage.getByPlaceholder(
    'Search receipt ID, college, subject...',
  );
  await search.fill(receiptId);
  await search.press('Enter');
  await expect(officerPage.getByText(receiptId, { exact: true })).toBeVisible();
  await officerPage.getByRole('link', { name: 'Examine' }).click();
  await expect(officerPage.getByText('Student Cell', { exact: true })).toBeVisible();
  await expect(officerPage.getByText('Why matched', { exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    officerPage.getByText('Technical Education', { exact: true }),
  ).toBeVisible();
  await officerPage.getByRole('button', { name: /confirm link/i }).click();
  await expect(officerPage.getByText('Decision: CONFIRMED')).toBeVisible();

  const otherBureauContext = await browser.newContext();
  const otherBureauPage = await otherBureauContext.newPage();
  await signIn(otherBureauPage, 'official.te@drishti.test');
  await expect(otherBureauPage).toHaveURL(/official\/inbox/);
  await otherBureauPage
    .getByRole('button', { name: /notifications/i })
    .click();
  await expect(
    otherBureauPage.getByRole('button', {
      name: /notification: Cross-Bureau Case Link Confirmed/i,
    }),
  ).toBeVisible();
  await expect(otherBureauPage.getByText(receiptId)).toBeVisible();

  await officerPage.getByRole('button', { name: 'Update Status' }).click();
  await officerPage.getByRole('combobox').selectOption({ label: 'In Progress' });
  await officerPage.getByRole('button', { name: 'Apply Status' }).click();
  await expect(officerPage.getByText('In Progress', { exact: true })).toBeVisible();
  await officerPage.getByRole('button', { name: 'Close & Determine' }).click();
  await officerPage
    .getByPlaceholder(
      'Detail the investigative findings, actions taken against institution, or reason for dismissal...',
    )
    .fill('Corrective action was verified by the reviewing officer.');
  await officerPage
    .getByRole('button', { name: 'Confirm Closure & Notify' })
    .click();
  await expect(
    officerPage.getByText('Official Determination: Accepted'),
  ).toBeVisible();
  await expect(officerPage.getByText('Closed', { exact: true })).toBeVisible();

  await Promise.all([
    complainantContext.close(),
    officerContext.close(),
    otherBureauContext.close(),
  ]);
});
