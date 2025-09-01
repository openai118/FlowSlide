<#
Push local working-tree changes to GitHub using the REST API (Contents API).

Usage:
  # set token in env (do NOT hard-code)
  $env:GITHUB_TOKEN = '<your_token_here>'
  # run script
  pwsh .\scripts\git_api_push.ps1

Requirements:
 - A GitHub personal access token with repo scope in GITHUB_TOKEN env var
 - A remote named 'origin' pointing to GitHub
 - Run from the repository root

Behavior:
 - Reads `git status --porcelain` to find added/modified/deleted files
 - For adds/modifies, calls PUT /repos/:owner/:repo/contents/:path
 - For deletes, calls DELETE /repos/:owner/:repo/contents/:path
 - Commits are created on the current branch

Notes:
 - This simple implementation doesn't handle renames specially (treated as delete+create)
 - Binary files are supported (encoded as base64)
#>

Param()

function Fail([string]$msg) { Write-Error $msg; exit 1 }

$token = $env:GITHUB_TOKEN
if (-not $token) { Fail "Environment variable GITHUB_TOKEN is required (personal access token with repo scope)." }

try { $remoteUrl = (git remote get-url origin) -replace "`r|`n","" } catch { Fail "Failed to get git remote 'origin'. Ensure you're in a git repo and remote 'origin' exists." }

# parse owner/repo from remote URL
if ($remoteUrl -match 'github.com[:/](.+?)(?:\.git)?$') { $repoFull = $matches[1] } else { Fail "Unsupported remote URL format: $remoteUrl" }

try { $branch = (git rev-parse --abbrev-ref HEAD) -replace "`r|`n","" } catch { Fail "Failed to get current branch" }

Write-Host "Repo: $repoFull  Branch: $branch"

$statusLines = git status --porcelain
if (-not $statusLines) { Write-Host "No changes to push via API."; exit 0 }

function Get-FileSha($path) {
    $encPath = [System.Uri]::EscapeDataString($path)
    $url = "https://api.github.com/repos/$repoFull/contents/$encPath?ref=$branch"
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "token $token"; 'User-Agent' = 'flowslide-git-api' } -Method Get
        return $resp.sha
    } catch {
        return $null
    }
}

function Api-PutFile($path, $contentB64, $message, $sha) {
    $encPath = [System.Uri]::EscapeDataString($path)
    $url = "https://api.github.com/repos/$repoFull/contents/$encPath"
    $body = @{ message = $message; content = $contentB64; branch = $branch }
    if ($sha) { $body.sha = $sha }
    $json = $body | ConvertTo-Json -Depth 6
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "token $token"; 'User-Agent' = 'flowslide-git-api' } -Method Put -Body $json -ContentType 'application/json'
        return $resp
    } catch {
        Write-Error "Failed to PUT $path : $($_.Exception.Message)"
        return $null
    }
}

function Api-DeleteFile($path, $sha, $message) {
    $encPath = [System.Uri]::EscapeDataString($path)
    $url = "https://api.github.com/repos/$repoFull/contents/$encPath"
    $body = @{ message = $message; sha = $sha; branch = $branch } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "token $token"; 'User-Agent' = 'flowslide-git-api' } -Method Delete -Body $body -ContentType 'application/json'
        return $resp
    } catch {
        Write-Error "Failed to DELETE $path : $($_.Exception.Message)"
        return $null
    }
}

$summary = @()

foreach ($line in $statusLines) {
    # porcelain: XY path (or XY path -> newpath)
    $raw = $line -replace "`r|`n",""
    if ($raw -match '^(..)\s+(.*)$') {
        $code = $matches[1]
        $path = $matches[2].Trim()
        # handle rename format 'old -> new'
        if ($path -match '^(.*) -> (.*)$') { $path = $matches[2].Trim() }

        # skip .gitignored or submodule lines
        if ($path -match '^\.git/') { continue }

        if ($code -match 'D') {
            # deletion
            Write-Host "Deleting: $path"
            $sha = Get-FileSha $path
            if (-not $sha) { Write-Warning "File not found on remote, skipping delete: $path"; continue }
            $res = Api-DeleteFile $path $sha "Delete $path via API"
            if ($res) { $summary += "Deleted $path" }
        } else {
            # addition or modification (A, M, ??)
            if (-not (Test-Path $path)) { Write-Warning "Local file missing, skipping: $path"; continue }
            Write-Host "Uploading: $path"
            try {
                $bytes = [System.IO.File]::ReadAllBytes($path)
                $b64 = [System.Convert]::ToBase64String($bytes)
            } catch {
                Write-Error "Failed to read $path: $($_.Exception.Message)"; continue
            }

            $sha = Get-FileSha $path
            $res = Api-PutFile $path $b64 "Update $path via API" $sha
            if ($res) { $summary += "Upserted $path" }
        }
    }
}

Write-Host "\nPush summary:"; $summary | ForEach-Object { Write-Host " - $_" }

Write-Host "Done. Note: this script updates files via the GitHub Contents API per-file. It does not update branch protections, tags or refs other than creating commits on the current branch." 
