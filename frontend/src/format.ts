export const soles = (n: number) =>
  n.toLocaleString("es-PE", {
    style: "currency",
    currency: "PEN",
    maximumFractionDigits: 0,
  });

export const soles2 = (n: number) =>
  n.toLocaleString("es-PE", {
    style: "currency",
    currency: "PEN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
