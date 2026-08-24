/**
 * Progressive spatial story for the product home.
 *
 * The poster and semantic HTML are the page. Canvas 2D adds a light system
 * diagram immediately; Three.js is imported only on a capable desktop. A
 * failed import, WebGL2 context, reduced-motion preference or data-saver mode
 * leaves the complete page and every product entrance intact.
 */
(() => {
  'use strict';

  const stage = document.getElementById('livingSystem');
  const canvas = document.getElementById('livingSystemCanvas');
  const threeCanvas = document.getElementById('livingSystemThree');
  if (!stage || !(canvas instanceof HTMLCanvasElement) || !(threeCanvas instanceof HTMLCanvasElement)) return;

  const controls = Array.from(document.querySelectorAll('[data-system-target]'));
  const mapNodes = Array.from(document.querySelectorAll('[data-system-node]'));
  const chapters = Array.from(document.querySelectorAll('[data-system-chapter]'));
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const desktopQuery = window.matchMedia('(min-width: 900px)');
  const lightQuery = window.matchMedia('(prefers-color-scheme: light)');
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const context = canvas.getContext('2d', { alpha: true });

  let active = 0;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let frame = 0;
  let controller = null;
  let importStarted = false;
  let visible = true;

  const palette = () => {
    const styles = getComputedStyle(document.documentElement);
    return {
      amber: styles.getPropertyValue('--family-amber').trim() || '#F5B335',
      paper: styles.getPropertyValue('--warm-paper').trim() || '#F7F5F2',
      navy: styles.getPropertyValue('--family-navy').trim() || '#0E1729',
    };
  };

  const resizeCanvas = () => {
    if (!context) return;
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = Math.max(1, canvas.clientWidth);
    height = Math.max(1, canvas.clientHeight);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw2d(performance.now());
  };

  const nodePositions = () => [
    [width * 0.28, height * 0.31],
    [width * 0.72, height * 0.31],
    [width * 0.28, height * 0.69],
    [width * 0.72, height * 0.69],
  ];

  const roundedRect = (x, y, w, h, radius) => {
    context.beginPath();
    context.moveTo(x + radius, y);
    context.lineTo(x + w - radius, y);
    context.quadraticCurveTo(x + w, y, x + w, y + radius);
    context.lineTo(x + w, y + h - radius);
    context.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    context.lineTo(x + radius, y + h);
    context.quadraticCurveTo(x, y + h, x, y + h - radius);
    context.lineTo(x, y + radius);
    context.quadraticCurveTo(x, y, x + radius, y);
    context.closePath();
  };

  function draw2d(time) {
    if (!context || controller) return;
    const colors = palette();
    const reduced = motionQuery.matches;
    const drift = reduced ? 0 : Math.sin(time / 2100) * Math.min(width, height) * 0.008;
    const centre = [width * 0.5, height * 0.5 + drift];
    const nodes = nodePositions();
    context.clearRect(0, 0, width, height);

    context.save();
    context.globalAlpha = 0.22;
    context.strokeStyle = colors.paper;
    context.lineWidth = 0.7;
    const horizon = height * 0.43;
    for (let index = -7; index <= 7; index += 1) {
      context.beginPath();
      context.moveTo(centre[0], horizon);
      context.lineTo(centre[0] + index * width * 0.11, height);
      context.stroke();
    }
    for (let index = 0; index < 9; index += 1) {
      const progress = index / 8;
      const y = horizon + progress * progress * (height - horizon);
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }
    context.restore();

    nodes.forEach(([x, y], index) => {
      const selected = index === active;
      context.save();
      context.strokeStyle = colors.amber;
      context.globalAlpha = selected ? 0.96 : 0.32;
      context.lineWidth = selected ? 2 : 1;
      context.beginPath();
      context.moveTo(centre[0], centre[1]);
      const bend = (x - centre[0]) * 0.18;
      context.bezierCurveTo(centre[0] + bend, centre[1], x - bend, y, x, y);
      context.stroke();

      const nodeWidth = Math.max(62, Math.min(104, width * 0.14));
      const nodeHeight = nodeWidth * 0.64;
      roundedRect(x - nodeWidth / 2, y - nodeHeight / 2, nodeWidth, nodeHeight, 10);
      context.fillStyle = selected ? 'rgba(245,179,53,.12)' : 'rgba(14,23,41,.16)';
      context.fill();
      context.stroke();
      context.restore();
    });

    context.save();
    context.translate(centre[0], centre[1]);
    context.strokeStyle = colors.amber;
    context.fillStyle = 'rgba(14,23,41,.48)';
    context.lineWidth = 1.4;
    context.globalAlpha = 0.94;
    context.beginPath();
    context.arc(0, 0, Math.max(25, Math.min(width, height) * 0.07), 0, Math.PI * 2);
    context.fill();
    context.stroke();
    context.rotate(reduced ? 0 : time / 8400);
    context.beginPath();
    context.moveTo(0, -11);
    context.quadraticCurveTo(2, -2, 11, 0);
    context.quadraticCurveTo(2, 2, 0, 11);
    context.quadraticCurveTo(-2, 2, -11, 0);
    context.quadraticCurveTo(-2, -2, 0, -11);
    context.fillStyle = colors.paper;
    context.fill();
    context.restore();
  }

  const syncActive = (index) => {
    active = Math.max(0, Math.min(3, Number(index) || 0));
    controls.forEach((control) => {
      control.toggleAttribute('data-active', Number(control.dataset.systemTarget) === active);
    });
    mapNodes.forEach((node) => {
      node.toggleAttribute('data-active', Number(node.dataset.systemNode) === active);
    });
    if (controller) controller.setActive(active);
    else draw2d(performance.now());
  };

  controls.forEach((control) => {
    const activate = () => syncActive(control.dataset.systemTarget);
    control.addEventListener('focus', activate);
    control.addEventListener('pointerenter', activate);
  });

  if ('IntersectionObserver' in window && chapters.length) {
    const chapterObserver = new IntersectionObserver((entries) => {
      const candidates = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (candidates[0]) syncActive(candidates[0].target.dataset.systemChapter);
    }, { rootMargin: '-28% 0px -46%', threshold: [0.2, 0.45, 0.7] });
    chapters.forEach((chapter) => chapterObserver.observe(chapter));
  }

  const supportsWebGL2 = () => {
    try {
      const probe = document.createElement('canvas');
      const gl = probe.getContext('webgl2', {
        failIfMajorPerformanceCaveat: true,
        powerPreference: 'low-power',
      });
      if (!gl) return false;
      const loseContext = gl.getExtension('WEBGL_lose_context');
      if (loseContext) loseContext.loseContext();
      return true;
    } catch (error) {
      return false;
    }
  };

  const shouldLoadThree = () => (
    !motionQuery.matches
    && desktopQuery.matches
    && window.innerWidth >= 900
    && !(connection && connection.saveData)
    && supportsWebGL2()
  );

  const returnToCanvas = () => {
    if (controller) controller.dispose();
    controller = null;
    stage.classList.remove('three-ready');
    stage.dataset.renderer = 'canvas';
    resizeCanvas();
    start2d();
  };

  const loadThree = async () => {
    if (importStarted || !shouldLoadThree()) return;
    importStarted = true;
    const moduleUrl = stage.dataset.threeModule;
    if (!moduleUrl) return;
    try {
      const module = await import(moduleUrl);
      if (!shouldLoadThree()) {
        importStarted = false;
        return;
      }
      controller = module.initLivingSystem({
        canvas: threeCanvas,
        stage,
        theme: lightQuery.matches ? 'light' : 'dark',
        assets: [stage.dataset.artA, stage.dataset.artB].filter(Boolean),
        onFallback: returnToCanvas,
      });
      controller.setActive(active);
      stage.classList.add('three-ready');
      stage.dataset.renderer = 'three';
      window.cancelAnimationFrame(frame);
      frame = 0;
      window.setTimeout(() => {
        if (controller && !shouldLoadThree()) returnToCanvas();
      }, 250);
    } catch (error) {
      stage.dataset.renderer = 'canvas';
      controller = null;
      draw2d(performance.now());
    }
  };

  function animate2d(time) {
    frame = 0;
    if (controller || !visible) return;
    draw2d(time);
    if (!motionQuery.matches) frame = window.requestAnimationFrame(animate2d);
  }

  function start2d() {
    if (!frame && !controller && visible) frame = window.requestAnimationFrame(animate2d);
  }

  let stageObserver = null;
  if ('IntersectionObserver' in window) {
    stageObserver = new IntersectionObserver((entries) => {
      visible = entries.some((entry) => entry.isIntersecting);
      if (visible) start2d();
      else {
        window.cancelAnimationFrame(frame);
        frame = 0;
      }
    }, { rootMargin: '120px' });
    stageObserver.observe(stage);
  }

  const onMotionChange = () => {
    if (motionQuery.matches && controller) returnToCanvas();
    if (!motionQuery.matches) loadThree();
    draw2d(performance.now());
    start2d();
  };
  motionQuery.addEventListener('change', onMotionChange);
  desktopQuery.addEventListener('change', (event) => {
    if (!event.matches && controller) returnToCanvas();
    if (event.matches) loadThree();
  });
  lightQuery.addEventListener('change', () => {
    if (controller) controller.dispose();
    controller = null;
    importStarted = false;
    stage.classList.remove('three-ready');
    stage.dataset.renderer = 'canvas';
    resizeCanvas();
    loadThree();
  });

  const resizeObserver = new ResizeObserver(resizeCanvas);
  resizeObserver.observe(stage);
  stage.dataset.renderer = 'canvas';
  syncActive(0);
  resizeCanvas();
  start2d();
  window.setTimeout(loadThree, 60);

  window.addEventListener('pagehide', () => {
    window.cancelAnimationFrame(frame);
    if (stageObserver) stageObserver.disconnect();
    resizeObserver.disconnect();
    if (controller) controller.dispose();
  }, { once: true });
})();
