/* Highlight the section currently in view without hijacking native anchors.
   Both public section navs use their real fragment links as the source. */
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nx-section-nav, .services-jump-links').forEach((nav) => {
      const pairs = [...nav.querySelectorAll('a[href^="#"]')]
        .map((link) => ({ link, target: document.getElementById(link.hash.slice(1)) }))
        .filter(({ target }) => target);
      if (!pairs.length) return;

      let scheduled = false;
      const sync = () => {
        scheduled = false;
        const activationLine = parseFloat(getComputedStyle(document.documentElement).fontSize) * 11;
        let current = pairs[0];
        for (const pair of pairs) {
          if (pair.target.getBoundingClientRect().top <= activationLine) current = pair;
        }
        for (const { link } of pairs) {
          if (link === current.link) link.setAttribute('aria-current', 'location');
          else link.removeAttribute('aria-current');
        }
      };
      const schedule = () => {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(sync);
      };
      window.addEventListener('scroll', schedule, { passive: true });
      window.addEventListener('resize', schedule, { passive: true });
      window.addEventListener('hashchange', schedule);
      sync();
    });
  });
})();
