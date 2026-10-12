<?php
// Mirror the NodePrism asset library from its GitHub Pages site into a folder
// on a PHP web server (the STRATO server's tool dispatcher runs it as a tool):
//
//   <target>/index.html, review.html, *.js, *.css   gallery and review page
//   <target>/library/objects/<category>/<id>.glb    only GLBs per category
//   <target>/library/images/, sounds/, videos/      other assets, added on the server
//   <target>/metadata/<id>/meta.json, preview.webp
//   <target>/index.json, library.json               catalogue built on GitHub
//   <target>/catalog.php                            index.json plus GLBs that exist only here
//   <target>/.htaccess                              MIME types and CORS for apps
//
// library/ holds only the assets themselves, so apps can list it.
//
// Only static files with known extensions and checked paths come from GitHub;
// catalog.php and .htaccess come from this file. Nothing is deleted, so models
// put on the server by hand stay. Afterwards folders get 0755 and files 0644,
// so uploads from Windows (0700) become readable for the web server.
//
// Args: target (default www/1b1library), source (default the Pages site),
// force (download every GLB even if its size matches).
// Source of truth: tools/mirror/syncNodeprismLibrary.php in r01b1/nodeprismvr-assets.

const NPL_SOURCE = 'https://r01b1.github.io/nodeprismvr-assets/';
const NPL_TARGET = 'www/1b1library';
const NPL_ID = '[a-z0-9]+(?:-[a-z0-9]+)*';
const NPL_ASSETS = 'library';  // GitHub's objects/... lands in <target>/library/objects/...

const NPL_HTACCESS = <<<'TXT'
# Written by syncNodeprismLibrary (nodeprismvr-assets mirror).
AddType model/gltf-binary .glb
AddType image/webp .webp
<IfModule mod_headers.c>
  <FilesMatch "\.(glb|gltf|json|webp|png|jpe?g|gif|svg|ktx2|hdr|mp3|ogg|oga|wav|m4a|aac|flac|mp4|webm|ogv|mov)$">
    Header set Access-Control-Allow-Origin "*"
  </FilesMatch>
</IfModule>

TXT;

const NPL_CATALOG = <<<'PHP'
<?php
// Library catalogue of this mirror: index.json from GitHub plus GLBs that
// exist only on this server in library/objects/<category>/, described by their own
// metadata/<id>/meta.json and preview.webp if those exist (no stats).
// Written by syncNodeprismLibrary (nodeprismvr-assets mirror).
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache');
header('Access-Control-Allow-Origin: *');
$index = json_decode((string)@file_get_contents(__DIR__ . '/index.json'), true);
if (!is_array($index)) $index = [];
$assets = is_array($index['assets'] ?? null) ? $index['assets'] : [];
$known = [];
foreach ($assets as $asset) $known[$asset['file'] ?? ''] = true;
foreach (glob(__DIR__ . '/library/objects/*/*.glb') ?: [] as $path) {
    $category = basename(dirname($path));
    $id = basename($path, '.glb');
    $file = 'library/objects/' . $category . '/' . basename($path);
    if (isset($known[$file])) continue;
    $meta = json_decode((string)@file_get_contents(__DIR__ . "/metadata/$id/meta.json"), true);
    if (!is_array($meta)) $meta = [];
    $text = fn($key, $default) => is_string($meta[$key] ?? null) ? $meta[$key] : $default;
    $preview = "metadata/$id/preview.webp";
    $assets[] = [
        'id' => $id, 'category' => $category, 'name' => $text('name', ucwords(str_replace(['-', '_'], ' ', $id))),
        'description' => $text('description', ''),
        'tags' => array_values(array_filter(is_array($meta['tags'] ?? null) ? $meta['tags'] : [], 'is_string')),
        'author' => $text('author', ''), 'license' => null, 'added' => date('Y-m-d', filemtime($path)),
        'file' => $file, 'preview' => is_file(__DIR__ . '/' . $preview) ? $preview : null, 'source' => null,
        'bytes' => filesize($path), 'triangles' => null, 'vertices' => null, 'materials' => [],
        'dimensions' => null, 'extensions' => [], 'serverOnly' => true,
    ];
}
$categories = array_values(array_unique(array_column($assets, 'category')));
sort($categories);
$index['categories'] = $categories;
$index['assets'] = $assets;
echo json_encode($index, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

PHP;

function npl_fetch(string $url): array {
    $url .= (strpos($url, '?') === false ? '?' : '&') . 't=' . time();  // Skip stale caches.
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_CONNECTTIMEOUT => 15, CURLOPT_TIMEOUT => 120,
            CURLOPT_USERAGENT => 'syncNodeprismLibrary/1.0',
        ]);
        $body = curl_exec($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        if ($body === false || $code >= 400) return [null, "$url: " . ($error ?: "HTTP $code")];
        return [$body, null];
    }
    $body = @file_get_contents($url, false, stream_context_create(['http' => ['timeout' => 120]]));
    return $body === false ? [null, "$url: download failed"] : [$body, null];
}

function npl_write(string $path, string $data): bool {
    $dir = dirname($path);
    if (!is_dir($dir) && !@mkdir($dir, 0755, true)) return false;
    $tmp = $path . '.part';
    if (@file_put_contents($tmp, $data) !== strlen($data)) return false;
    return @rename($tmp, $path);  // Visitors never see half a file.
}

function npl_fix_permissions(string $root): int {
    $changed = 0;
    $items = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::SELF_FIRST);
    foreach (array_merge([new SplFileInfo($root)], iterator_to_array($items, false)) as $item) {
        $want = $item->isDir() ? 0755 : 0644;
        if ((fileperms($item->getPathname()) & 0777) !== $want && @chmod($item->getPathname(), $want)) $changed++;
    }
    return $changed;
}

function execute_syncNodeprismLibrary(array $a): array {
    @set_time_limit(600);
    $target = (string)($a['target'] ?? NPL_TARGET);
    $source = rtrim((string)($a['source'] ?? NPL_SOURCE), '/') . '/';
    $force = !empty($a['force']);
    if (!preg_match('#^www/[A-Za-z0-9._-]+$#', $target) || strpos($target, '..') !== false) {
        return ['success' => false, 'error' => 'target must be a folder directly in www/'];
    }
    if (!preg_match('#^(https://|http://(127\.0\.0\.1|localhost)[:/])#', $source)) {
        return ['success' => false, 'error' => 'source must be https'];
    }

    $errors = [];
    $written = [];
    $skipped = 0;
    $get = function (string $url, string $path, ?callable $valid = null) use (&$errors, &$written): bool {
        [$body, $error] = npl_fetch($url);
        if ($error !== null) { $errors[] = $error; return false; }
        if ($valid && !$valid($body)) { $errors[] = "$url: unexpected content"; return false; }
        if (!npl_write($path, $body)) { $errors[] = "$path: write failed"; return false; }
        $written[] = $path;
        return true;
    };

    [$indexBody, $error] = npl_fetch($source . 'library/index.json');
    $index = $error === null ? json_decode($indexBody, true) : null;
    if (!is_array($index) || !is_array($index['assets'] ?? null)) {
        return ['success' => false, 'error' => $error ?? 'library/index.json is not a catalogue'];
    }
    [$filesBody, $error] = npl_fetch($source . 'site-files.json');
    $siteFiles = $error === null ? json_decode($filesBody, true) : null;
    if (!is_array($siteFiles)) return ['success' => false, 'error' => $error ?? 'site-files.json is not a list'];

    // The library: GLBs, previews, metadata.
    $isGlb = fn($b) => substr($b, 0, 4) === 'glTF';
    $isWebp = fn($b) => substr($b, 0, 4) === 'RIFF' && substr($b, 8, 4) === 'WEBP';
    $isJson = fn($b) => is_array(json_decode($b, true));
    foreach ($index['assets'] as $asset) {
        $id = (string)($asset['id'] ?? '');
        $file = (string)($asset['file'] ?? '');
        $preview = (string)($asset['preview'] ?? '');
        if (!preg_match('#^' . NPL_ID . '$#', $id)
            || !preg_match('#^objects/' . NPL_ID . '/' . preg_quote($id, '#') . '\.glb$#', $file)
            || $preview !== "metadata/$id/preview.webp") {
            $errors[] = "skipped catalogue entry with unexpected paths: $id";
            continue;
        }
        $glb = "$target/" . NPL_ASSETS . "/$file";
        if (!$force && is_file($glb) && filesize($glb) === (int)($asset['bytes'] ?? -1)) {
            $skipped++;
        } else {
            $get($source . 'library/' . $file, $glb, $isGlb);
        }
        $get($source . 'library/' . $preview, "$target/$preview", $isWebp);
        $get($source . "library/metadata/$id/meta.json", "$target/metadata/$id/meta.json", $isJson);
    }
    $get($source . 'library/library.json', "$target/library.json", $isJson);
    // The catalogue next to the pages, with GLB paths pointing into library/.
    foreach ($index['assets'] as &$asset) {
        if (is_string($asset['file'] ?? null)) $asset['file'] = NPL_ASSETS . '/' . $asset['file'];
    }
    unset($asset);
    $indexBody = json_encode($index, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if (npl_write("$target/index.json", $indexBody)) $written[] = "$target/index.json";
    else $errors[] = "$target/index.json: write failed";

    // The website, pointed at catalog.php instead of library/index.json.
    foreach ($siteFiles as $name) {
        if (!is_string($name) || !preg_match('#^[A-Za-z0-9][A-Za-z0-9._-]*\.(html|js|css)$#', $name)) {
            $errors[] = 'skipped site file with an unexpected name';
            continue;
        }
        [$body, $error] = npl_fetch($source . $name);
        if ($error !== null) { $errors[] = $error; continue; }
        if (substr($name, -5) === '.html') {
            $body = preg_replace('#(<meta name="library-catalog" content=")[^"]*(")#', '${1}catalog.php${2}', $body);
        }
        if (npl_write("$target/$name", $body)) $written[] = "$target/$name";
        else $errors[] = "$target/$name: write failed";
    }
    foreach (['.htaccess' => NPL_HTACCESS, 'catalog.php' => NPL_CATALOG] as $name => $content) {
        if (npl_write("$target/$name", $content)) $written[] = "$target/$name";
        else $errors[] = "$target/$name: write failed";
    }

    return [
        'success' => !$errors,
        'target' => $target,
        'url' => isset($_SERVER['HTTP_HOST']) ? 'https://' . $_SERVER['HTTP_HOST'] . '/files/' . $target . '/' : null,
        'assets' => count($index['assets']),
        'written' => count($written),
        'unchangedGlbs' => $skipped,
        'permissionsFixed' => is_dir($target) ? npl_fix_permissions($target) : 0,
        'errors' => $errors,
    ];
}
