// Replace oldDomain with newDomain
const oldDomain = 'canonical-maas.readthedocs-hosted.com';
const newDomain = 'canonical.com/maas/docs';

// Use a MutationObserver to wait for the RTD flyout element to appear in the DOM
const observer = new MutationObserver(function (mutations, obs) {
  const rtdFlyout = document.querySelector('readthedocs-flyout');
  if (!rtdFlyout) return;

  obs.disconnect();

  rtdFlyout.addEventListener('click', function () {
    const shadowRoot = rtdFlyout.shadowRoot;
    if (!shadowRoot) return;

    const anchors = shadowRoot.querySelectorAll('a');
    anchors.forEach(anchor => {
      anchor.href = anchor.href.replace(new RegExp(oldDomain, 'g'), newDomain);
    });
  });
});

observer.observe(document.body, { childList: true, subtree: true });

// Overwrite the GitHub feedback link with a Launchpad bug report link.
const feedbackObserver = new MutationObserver(function (mutations, obs) {
  const feedbackLink = document.querySelector('.github-issue-link');
  if (!feedbackLink) return;

  obs.disconnect();

  feedbackLink.href = (
    "https://bugs.launchpad.net/maas/+filebug?"
  );
});

feedbackObserver.observe(document.body, { childList: true, subtree: true });
