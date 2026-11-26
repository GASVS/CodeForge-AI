import '@testing-library/jest-dom/vitest';

// jsdom has no layout engine — scrollIntoView is a not-implemented stub there.
Element.prototype.scrollIntoView = function scrollIntoView() { /* noop */ };
