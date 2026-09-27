-- Pandoc Lua filter for tools/latex/conspect.tex.
-- Markdown conventions it understands (see .claude/commands/lecture.md, step 6–7):
--   ::: {.abstract title="…"} / ::: keypoints / ::: emphasis / ::: watch / ::: {.qa title="…"} -> tcolorbox environments
--   *Таймкод: ЧЧ:ММ:СС · слайды …*  (a paragraph of its own)            -> \secmeta badge
--   [^n]: Примечание составителя: …                                      -> footnote with a styled label
--   **Акцент лектора:** / **Важный вывод:** / **Важно:**                 -> red inline label
--   table header cells                                                   -> \tablehead{…}

local function raw(s) return pandoc.RawBlock('latex', s) end
local function rawi(s) return pandoc.RawInline('latex', s) end

local function tex_escape(s)
  return (s:gsub('\\', '\\textbackslash{}'):gsub('([#$%%&_{}])', '\\%1'))
end

local boxes = { abstract = 'abstractbox', keypoints = 'keypointsbox',
                emphasis = 'emphasisbox', watch = 'watchbox', plan = 'planbox',
                qa = 'qabox' }

function Div(el)
  for _, c in ipairs(el.classes) do
    local env = boxes[c]
    if env then
      local title = tex_escape(el.attributes.title or '')
      local out = { raw('\\begin{' .. env .. '}{' .. title .. '}') }
      for _, b in ipairs(el.content) do out[#out + 1] = b end
      out[#out + 1] = raw('\\end{' .. env .. '}')
      return out
    end
  end
end

function Para(el)
  if #el.content == 1 and el.content[1].t == 'Emph' then
    local txt = pandoc.utils.stringify(el.content[1])
    local tc, rest = txt:match('^Таймкод:%s*([%d:–%-]+)%s*·%s*(.*)$')
    if tc then
      return raw('\\secmeta{' .. tex_escape(tc) .. '}{' .. tex_escape(rest) .. '}')
    end
  end
end

local labels = { ['Акцент лектора:'] = true, ['Важный вывод:'] = true, ['Важно:'] = true }

function Strong(el)
  local s = pandoc.utils.stringify(el)
  if labels[s] then return rawi('\\lectmark{' .. s .. '}') end
end

function Note(el)
  local first = el.content[1]
  if first and first.t == 'Para' and pandoc.utils.stringify(first):find('^Примечание составителя:') then
    local c, i = first.content, 1
    while c[i] and not (c[i].t == 'Str' and c[i].text == 'составителя:') do i = i + 1 end
    local newc = { rawi('\\compnote{}') }
    for j = i + 2, #c do newc[#newc + 1] = c[j] end
    local w = newc[2]
    if w and w.t == 'Str' then  -- capitalize the first word after the label
      local head, tail = w.text:match('^([%z\1-\127\194-\244][\128-\191]*)(.*)$')
      if head then w.text = pandoc.text.upper(head) .. tail end
    end
    first.content = newc
  end
  return el
end

function Table(t)
  for _, row in ipairs(t.head.rows) do
    for _, cell in ipairs(row.cells) do
      for k, b in ipairs(cell.contents) do
        if b.t == 'Plain' or b.t == 'Para' then
          local inl = { rawi('\\tablehead{') }
          for _, x in ipairs(b.content) do inl[#inl + 1] = x end
          inl[#inl + 1] = rawi('}')
          cell.contents[k] = pandoc.Plain(inl)
        end
      end
    end
  end
  return t
end

-- pandoc hardcodes \labelenumi for explicit "1." lists; default attrs let enumitem style them
function OrderedList(el)
  el.listAttributes = pandoc.ListAttributes(el.start, 'DefaultStyle', 'DefaultDelim')
  return el
end

-- ---------- document-level pass: TOC page + glossary links ----------
--   * \tocpage is inserted before the first numbered section (separate clickable TOC page).
--   * Each glossary term (first cell of the table under "## Глоссарий") gets a link to its
--     first use in the numbered sections: an explicit span [текст]{.gl key="Термин"} wins,
--     otherwise the first **bold** text whose words start with the term's word stems,
--     otherwise the first paragraph containing them. A column "Впервые" with the page is added.

local ulower, ulen, usub = pandoc.text.lower, pandoc.text.len, pandoc.text.sub

local function words(s)
  s = ulower(s):gsub('ё', 'е')
  local ws = {}
  for w in s:gmatch("[%w\128-\255%-']+") do ws[#ws + 1] = w end
  return ws
end

local function stem(w)
  local n = ulen(w)
  if n >= 7 then return usub(w, 1, math.max(6, n - 2)) end
  return w
end

local function add_key(keys, s)
  s = s:gsub('^%s+', ''):gsub('%s+$', '')
  if s == '' then return end
  local st = {}
  for _, w in ipairs(words(s)) do st[#st + 1] = stem(w) end
  if #st > 1 or (#st == 1 and ulen(st[1]) >= 2) then keys[#keys + 1] = st end
end

local function term_keys(term)
  local keys = {}
  local base = term:gsub('%b()', '')
  base = base:gsub('%s+/%s+', '\0')  -- only " / " separates alternatives, "A/B" stays whole
  for part in (base .. '\0'):gmatch('([^%z]+)%z') do
    for p in (part .. ','):gmatch('([^,]+),') do add_key(keys, p) end
  end
  for inside in term:gmatch('%((.-)%)') do
    for p in (inside .. ','):gmatch('([^,]+),') do add_key(keys, p) end
  end
  return keys
end

local function starts(w, k) return w:sub(1, #k) == k end

-- any order: every stem of some key starts some word (for short bold spans)
local function matches_any_order(ws, keys)
  for _, k in ipairs(keys) do
    local all = true
    for _, kw in ipairs(k) do
      local hit = false
      for _, w in ipairs(ws) do if starts(w, kw) then hit = true; break end end
      if not hit then all = false; break end
    end
    if all then return true end
  end
  return false
end

-- contiguous, in order (for whole paragraphs)
local function matches(ws, keys)
  for _, k in ipairs(keys) do
    for i = 1, #ws - #k + 1 do
      local ok = true
      for j = 1, #k do
        if ws[i + j - 1]:sub(1, #k[j]) ~= k[j] then ok = false; break end
      end
      if ok then return true end
    end
  end
  return false
end

local function heading_text(b) return pandoc.utils.stringify(b.content) end

-- Block:walk() skips the root block itself; wrap it so top-level paragraphs are visited too.
-- Top-down order, footnotes are not searched.
local function walk_block(b, f)
  f.traverse = 'topdown'
  f.Note = function(n) return n, false end
  return pandoc.Div({ b }):walk(f).content[1]
end

local function structure(doc)
  local blocks = doc.blocks
  -- 1. glossary table
  local gl_table_idx
  for i, b in ipairs(blocks) do
    if b.t == 'Header' and heading_text(b):find('^Глоссарий') then
      for j = i + 1, #blocks do
        if blocks[j].t == 'Table' then gl_table_idx = j; break end
        if blocks[j].t == 'Header' then break end
      end
    end
  end
  local terms = {}
  if gl_table_idx then
    for r, row in ipairs(blocks[gl_table_idx].bodies[1].body) do
      local t = pandoc.utils.stringify(row.cells[1].contents)
      terms[#terms + 1] = { name = t, keys = term_keys(t), id = 'gl-' .. r, row = row }
    end
  end
  local by_name = {}
  for _, t in ipairs(terms) do by_name[ulower(t.name)] = t end

  -- 2. range of numbered sections
  local first, last
  for i, b in ipairs(blocks) do
    if b.t == 'Header' and b.level <= 2 then
      local numbered = not b.classes:includes('unnumbered')
      if numbered and not first then first = i end
      if first and not numbered and i > first and not last then last = i - 1 end
    end
  end
  last = last or #blocks

  -- 3a. explicit spans
  for i = first or 1, last do
    blocks[i] = walk_block(blocks[i], { Span = function(sp)
      if sp.classes:includes('gl') and sp.attributes.key then
        local t = by_name[ulower(sp.attributes.key)]
        if t and not t.found then
          t.found = 'явно'; sp.identifier = t.id; sp.classes = {}; sp.attributes = {}
          return sp
        end
      end
    end })
  end
  -- 3b. first bold occurrence, then first paragraph
  local function pending()
    local n = 0
    for _, t in ipairs(terms) do if not t.found then n = n + 1 end end
    return n
  end
  for i = first or 1, last do
    if pending() == 0 then break end
    blocks[i] = walk_block(blocks[i], { Strong = function(st)
      local ws = words(pandoc.utils.stringify(st))
      for _, t in ipairs(terms) do
        if not t.found and matches_any_order(ws, t.keys) then
          t.found = pandoc.utils.stringify(st)
          return pandoc.Span({ st }, pandoc.Attr(t.id)), false
        end
      end
    end })
  end
  for i = first or 1, last do
    if pending() == 0 then break end
    local function para(p)
      local txt = pandoc.utils.stringify(p.content:filter(function(x) return x.t ~= 'Note' end))
      local ws = words(txt)
      local anchors = {}
      for _, t in ipairs(terms) do
        if not t.found and matches(ws, t.keys) then
          t.found = '(абзац) ' .. usub(txt, 1, 50)
          anchors[#anchors + 1] = pandoc.Span({}, pandoc.Attr(t.id))
        end
      end
      if #anchors > 0 then
        for k = #anchors, 1, -1 do table.insert(p.content, 1, anchors[k]) end
        return p
      end
    end
    blocks[i] = walk_block(blocks[i], { Para = para, Plain = para })
  end

  -- 4. glossary: link terms, add "Впервые" column
  if gl_table_idx then
    local tbl = blocks[gl_table_idx]
    tbl.colspecs = { { 'AlignLeft', 0.30 }, { 'AlignLeft', 0.58 }, { 'AlignLeft', 0.12 } }
    for _, row in ipairs(tbl.head.rows) do
      row.cells[#row.cells + 1] = pandoc.Cell({ pandoc.Plain { pandoc.Str('Впервые') } })
    end
    for _, t in ipairs(terms) do
      local cell
      if t.found then
        local c1 = t.row.cells[1]
        c1.contents = { pandoc.Plain { pandoc.Link(pandoc.utils.blocks_to_inlines(c1.contents), '#' .. t.id) } }
        cell = pandoc.Plain { pandoc.RawInline('latex',
          '\\hyperref[' .. t.id .. ']{с.\\,\\pageref*{' .. t.id .. '}}') }
        io.stderr:write('glossary: ' .. t.name .. ' -> ' .. t.found .. '\n')
      else
        cell = pandoc.Plain { pandoc.Str('—') }
        io.stderr:write('glossary: NOT FOUND ' .. t.name .. ' (add [текст]{.gl key="' .. t.name .. '"})\n')
      end
      t.row.cells[#t.row.cells + 1] = pandoc.Cell({ cell })
    end
  end

  -- 5. TOC page before the first numbered section
  if first then table.insert(blocks, first, pandoc.RawBlock('latex', '\\tocpage')) end
  doc.blocks = blocks
  return doc
end

return {
  { Pandoc = structure },
  { Div = Div, Para = Para, Strong = Strong, Note = Note, Table = Table, OrderedList = OrderedList },
}
