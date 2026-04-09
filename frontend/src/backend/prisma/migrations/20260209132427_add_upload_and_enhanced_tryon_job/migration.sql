/*
  Warnings:

  - You are about to drop the column `apiJobId` on the `TryOnJob` table. All the data in the column will be lost.
  - You are about to drop the column `deleteAt` on the `TryOnJob` table. All the data in the column will be lost.
  - You are about to drop the column `resultPhotoUrl` on the `TryOnJob` table. All the data in the column will be lost.
  - You are about to drop the column `userPhotoUrl` on the `TryOnJob` table. All the data in the column will be lost.
  - Added the required column `productImageId` to the `TryOnJob` table without a default value. This is not possible if the table is not empty.
  - Added the required column `userImageId` to the `TryOnJob` table without a default value. This is not possible if the table is not empty.

*/
-- CreateTable
CREATE TABLE "Upload" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userId" TEXT,
    "filename" TEXT NOT NULL,
    "filepath" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_TryOnJob" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userId" TEXT,
    "productId" TEXT,
    "userImageId" TEXT NOT NULL,
    "productImageId" TEXT NOT NULL,
    "garmentType" TEXT,
    "mode" TEXT NOT NULL DEFAULT 'final',
    "realismLevel" INTEGER NOT NULL DEFAULT 3,
    "preserveFace" BOOLEAN NOT NULL DEFAULT true,
    "preserveBackground" BOOLEAN NOT NULL DEFAULT true,
    "status" TEXT NOT NULL DEFAULT 'QUEUED',
    "resultPath" TEXT,
    "qualityScore" REAL,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "retryCount" INTEGER NOT NULL DEFAULT 0,
    "maxRetries" INTEGER NOT NULL DEFAULT 2,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    CONSTRAINT "TryOnJob_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "TryOnJob_userImageId_fkey" FOREIGN KEY ("userImageId") REFERENCES "Upload" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "TryOnJob_productImageId_fkey" FOREIGN KEY ("productImageId") REFERENCES "Upload" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_TryOnJob" ("createdAt", "errorMessage", "id", "productId", "status", "updatedAt", "userId") SELECT "createdAt", "errorMessage", "id", "productId", "status", "updatedAt", "userId" FROM "TryOnJob";
DROP TABLE "TryOnJob";
ALTER TABLE "new_TryOnJob" RENAME TO "TryOnJob";
CREATE INDEX "TryOnJob_userId_idx" ON "TryOnJob"("userId");
CREATE INDEX "TryOnJob_status_idx" ON "TryOnJob"("status");
CREATE INDEX "TryOnJob_createdAt_idx" ON "TryOnJob"("createdAt");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE UNIQUE INDEX "Upload_filepath_key" ON "Upload"("filepath");
