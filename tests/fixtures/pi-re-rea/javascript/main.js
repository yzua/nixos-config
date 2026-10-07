// Static-only Electron fixture: never import or execute this module.
import { ipcMain } from "electron";
import { score } from "./score.js";

ipcMain.handle("rea:score", (_event, value) => score(value));
