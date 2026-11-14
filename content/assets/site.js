const links = [...document.querySelectorAll('.nav__links a[href^="#"]')];
const sections = links.map((link) => document.querySelector(link.getAttribute('href'))).filter(Boolean);

function markCurrent(id) {
  links.forEach((link) => {
    if (link.getAttribute('href') === `#${id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
}

if ('IntersectionObserver' in window && sections.length) {
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible) markCurrent(visible.target.id);
  }, { rootMargin: '-35% 0px -50% 0px', threshold: [0, 0.1, 0.5] });
  sections.forEach((section) => observer.observe(section));
}

links.forEach((link) => link.addEventListener('click', () => markCurrent(link.hash.slice(1))));
