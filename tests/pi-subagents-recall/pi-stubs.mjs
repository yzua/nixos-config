// Only registration/schema/UI seams are needed; there is no model runtime.
const schema = (value = {}) => value;
export const Type = { Object: schema, String: schema, Optional: schema };
export const keyHint = () => "";
export const truncateToWidth = (text, width) => text.slice(0, width);
export const visibleWidth = (text) => text.length;
export class Text { constructor() {} }
export class Box { constructor() {} }
