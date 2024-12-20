import os, sys, json, subprocess, string

def dump_blend(out):
    import bpy
    dump = {}
    objects = {}
    meshes = {}
    greases = {}
    fonts  = {}
    materials = {}
    collections = {}
    selected = []
    dump = {
        'objects':objects,
        'meshes':meshes,
        'greases':greases,
        'fonts':fonts,
        'materials':materials,
        'collections':collections,
        'selected':[],
        'active_object' : None,
    }
    if bpy.context.active_object:
        dump['active_object']=bpy.context.active_object.name
    if bpy.context.selected_objects:
        for ob in bpy.context.selected_objects:
            dump['selected'].append(ob.name)

    for col in bpy.data.collections:
        collections[col.name] = [ob.name for ob in col.objects]

    for ob in bpy.data.objects:
        p = None
        if ob.parent:
            p = ob.parent.name
        objects[ob.name] = {
            'pos':list(ob.location), 
            'rot':list(ob.rotation_euler), 
            'scl':list(ob.scale),
            'parent' : p
        }
        if ob.type=='MESH':
            info = {'data':ob.data.name, 'materials':[]}
            meshes[ob.name] = info
            for mat in ob.data.materials:
                info['materials'].append( {'name':mat.name, 'color':list(mat.diffuse_color)} )

        elif ob.type=='GPENCIL':
            greases[ob.name] = ob.data.name

    for mat in bpy.data.materials:
        r,g,b,a = mat.diffuse_color
        materials[mat.name] = {
            'color':[r,g,b,a],
        }

    print('saving:', out)
    open(out,'wb').write(json.dumps(dump).encode('utf-8'))

def render_blend(out):
    import bpy
    scn = bpy.data.scenes[0]
    scn.render.resolution_x = 128
    scn.render.resolution_y = 128
    scn.eevee.taa_render_samples = 4
    scn.render.filepath = out
    bpy.ops.render.render(write_still=True)

for arg in sys.argv:
    if arg.startswith('--dump-blend='):
        dump_blend(arg.split('=')[-1])
        sys.exit()
    elif arg.startswith('--render='):
        render_blend(arg.split('=')[-1])
        sys.exit()

from wordprocessor import *
import blender_thumbnailer as nailer

if sys.platform == 'win32':
    BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe'
    if not os.path.isfile(BLENDER):
        BLENDER = 'C:/Program Files/Blender Foundation/Blender 3.6/blender.exe'
elif sys.platform == 'darwin':
    BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
else:
    BLENDER = 'blender'
    if os.path.isfile(os.path.expanduser('~/Downloads/blender-4.2.1-linux-x64/blender')):
        BLENDER = os.path.expanduser('~/Downloads/blender-4.2.1-linux-x64/blender')


class MegasolidCodeEditor( MegasolidEditor ):
    def reset(self, x=100, y=100, width=960, height=600, use_icons=False, use_menu=False, alt_widget=None):
        self.tables = []
        self.blender_symbols = list(self.BLEND_SYMS)
        self.blend_syms = {}
        self.blend_thumbs = {}
        self.blend_files = {}
        layout = QVBoxLayout()
        container = QWidget()
        container.setLayout(layout)
        self.line_counts = QLabel('.')
        layout.addWidget(self.line_counts)
        layout.addStretch(1)
        self.left_widget = container
        self.images_layout = None
        self.qimages = {}
        self.blend_previews = {}

        layout = QVBoxLayout()
        container = QWidget()
        container.setLayout(layout)
        layout.addStretch(1)
        self.right_widget = container
        self.images_layout = layout
        self.alt_widget = alt_widget

        super(MegasolidCodeEditor,self).reset(
            x,y,width,height, 
            use_icons=use_icons, 
            use_menu=use_menu, 
            use_monospace=True, 
            allow_inline_tables=False)

        self.editor.tables = self.tables

        self.setStyleSheet('background-color:rgb(42,42,42); color:lightgrey')
        self.editor.setStyleSheet('background-color:rgb(42,42,42); color:white')

        self.editor.on_link_clicked = self.on_link_clicked
        self.editor.on_new_table = self.on_new_table
        self.editor.on_mouse_over_anchor = self.on_mouse_over_anchor
        self.editor.extra_mime_types = {
            '.blend' : self.on_new_blend,
        }
        self.blends = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.do_syntax_hl)
        self.timer.start(3000)
        self.prev_html = None
        self.use_syntax_highlight = True
        self.use_syntax_highlight_action = act = QAction("🗹", self)
        act.setToolTip("toggle syntax highlighting")
        act.setStatusTip("toggle syntax highlighting")
        act.setCheckable(True)
        act.setChecked(True)
        act.toggled.connect( lambda x,a=act: self.toggle_syntax_highlight(x,a) )
        self.format_toolbar.addAction(act)


        act = QAction("➤", self)
        act.setToolTip("run script in blender")
        act.setStatusTip("run script in blender")
        act.triggered.connect( self.run_script )
        self.format_toolbar.addAction(act)

        self.extra_syms = {}
        self.extra_syms_style = {}
        self.on_sym_clicked = {}
        self.on_syntax_highlight_post = None

        if sys.platform=='win32' and not os.path.isdir('/tmp'):
            os.mkdir('/tmp')


    def toggle_syntax_highlight(self, val, btn):
        self.use_syntax_highlight = val
        if val:
            btn.setText('🗹')
        else:
            btn.setText('🗶')

    SYNTAX_PY = {
        'def': 'cyan',
        'assert':'cyan',
        'for': 'red',
        'in' : 'red',
        'while': 'red',
        'if':'red',
        'elif':'red',
        'else':'red',
        'class':'red',
        'return':'red',
        'print' : 'cyan',
    }
    SYNTAX_C = {
        'void'   : 'yellow',
        'static' : 'yellow',
        'const'  : 'yellow',
        'struct' : 'yellow',
    }
    C_TYPES = ['char', 'short', 'int', 'long', 'float', 'double']
    for _ in C_TYPES: SYNTAX_C[_]='lightgreen'
    SYNTAX_C3 = {}
    C3_KEYWORDS = ['true', 'false', 'fn', 'extern', 'ichar', 'ushort', 'float16', 'bool', 'bitstruct', 'distinct', 'import']
    C3_ATTRS = ['@wasm', '@packed', '@adhoc', '@align', '@benchmark', '@bigendian', '@builtin', 
        '@callc', '@deprecated', '@export', '@finalizer', '@if', '@init', '@inline', '@littleendian',
        '@local', '@maydiscard', '@naked', '@nodiscard', '@noinit', '@norecurse', '@noreturn', '@nostrip',
        '@obfuscate', '@operator', '@overlap', '@private', '@pure', '@reflect', '@section', '@test',
        '@unused', '@weak',
    ]
    for _ in C3_KEYWORDS+C3_ATTRS: SYNTAX_C3[_]='pink'

    ZIG_TYPES = ['i%s'%i for i in (8,16,32,64,128)] + ['u%s'%i for i in (8,16,32,64,128)] + ['f16', 'f32', 'f64', 'f80', 'f128']
    ZIG_TYPES += 'isize usize c_char c_short c_ushort c_int c_uint c_long c_ulong c_longlong c_ulonglong anyopaque type anyerror comptime_int comptime_float'.split()
    SYNTAX_ZIG = {
        '@intCast' : 'orange',
        '@intFromFloat' : 'orange',
    }
    ZIG_KEYWORDS = 'defer null undefined try pub comptime var or callconv export'.split()
    for _ in ZIG_KEYWORDS + ZIG_TYPES: SYNTAX_ZIG[_]='orange'

    SYNTAX = {}
    SYNTAX.update(SYNTAX_PY)
    SYNTAX.update(SYNTAX_C)
    SYNTAX.update(SYNTAX_C3)
    SYNTAX.update(SYNTAX_ZIG)

    def has_keywords(self, txt):
        tokens = txt.split()
        for kw in self.SYNTAX:
            if kw in tokens:
                return True
        return False

    def tokenize(self, txt):
        toks = []
        for c in txt:
            #if c==self.OBJ_REP or c==self.OBJ_TABLE or c==self.OBJ_BLEND:
            if c==self.OBJ_REP or c==self.OBJ_TABLE or c in self.BLEND_SYMS:
                toks.append(c)
            elif c in (' ', '\t'):
                if not toks or type(toks[-1]) is not list:
                    toks.append([])
                toks[-1].append(c)
            elif c == '\n':
                toks.append(b'\n')
            elif c in '()[]{}:.-=+*&^%<>/|':
                toks.append(tuple([c]))
            else:
                if not toks or type(toks[-1]) is not str:
                    toks.append('')
                toks[-1] += c
        return toks

    ## https://qthub.com/static/doc/qt5/qtgui/qtextdocument.html#toPlainText
    ## Note: Embedded objects, such as images, are represented by a Unicode value U+FFFC (OBJECT REPLACEMENT CHARACTER).
    OBJ_REP = chr(65532)
    OBJ_TABLE = '▦' #'\x00'
    #OBJ_BLEND = '🮵'  ## no font on MS Windows for this :(
    BLEND_SYMS = 'ก ข ฃ ค ฅ ฆ ง จ ฉ ช ฌ ญ ฎ ฐ ฑ ฒ ณ ต ถ ธ ฤ ป ผ ฝ ฟ ภ ย ล ฦ ว ศ ษ ส ห ฬ อ ฮ ฯ'.split()
    def do_syntax_hl(self):
        if not self.use_syntax_highlight:
            return
        h = self.editor.toHtml()
        if h != self.prev_html:
            if '\x00' in h:
                ## this can happen on copy and paste from libreoffice a null byte at the end
                h = h.replace('\x00', '')

            try:
                d = xml.dom.minidom.parseString(h)
            except xml.parsers.expat.ExpatError as err:
                for i,ln in enumerate(h.splitlines()):
                   print(i+1,ln.encode('utf-8'))
                raise err

            #tables = [elt for elt in d.getElementsByTagName('table')]
            #if tables:
            #    self.tables = tables
            images = [img.getAttribute('src') for img in d.getElementsByTagName('img')]

            txt = self.editor.toPlainText()
            print('-'*80)
            print(txt.encode('utf-8'))
            print('_'*80)
            toks = self.tokenize(txt)
            print(toks)

            cur = self.editor.textCursor()
            pos = cur.position()
            doc = xml.dom.minidom.Document()
            p = doc.createElement('p')
            p.setAttribute('style', 'margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; white-space: pre-wrap;')
            img_index = 0
            tab_index = 0
            blend_index = 0
            nodes = []
            skip_imgs = []
            for tok in toks:
                if tok==self.OBJ_TABLE:
                    tab = self.tables[tab_index]
                    print(tab)
                    print(tab.toxml())
                    anchor = doc.createElement('a')
                    anchor.setAttribute('href', str(tab_index))
                    anchor.setAttribute('style', 'color:cyan')
                    anchor.appendChild(doc.createTextNode(self.OBJ_TABLE))
                    nodes.append(anchor)
                    tab_index += 1
                elif type(tok) is str and tok in self.BLEND_SYMS:
                    info = self.blends[blend_index]
                    anchor = doc.createElement('a')
                    anchor.setAttribute('href', 'BLENDER:%s' % blend_index)
                    anchor.setAttribute('style', 'color:cyan; font-size:32px;')
                    anchor.appendChild(doc.createTextNode(tok))
                    if tok in self.blend_thumbs:
                        img = doc.createElement('img')
                        img.setAttribute('src', self.blend_thumbs[tok])
                        img.setAttribute('width','32')
                        img.setAttribute('height','32')
                        skip_imgs.append(self.blend_thumbs[tok])
                        anchor.appendChild(img)
                    nodes.append(anchor)
                    blend_index += 1
                elif type(tok) is str and tok in self.extra_syms:
                    anchor = doc.createElement('a')
                    anchor.setAttribute('href', tok)
                    if tok in self.extra_syms_style:
                        anchor.setAttribute('style', self.extra_syms_style[tok])
                    else:
                        anchor.setAttribute('style', 'color:cyan; font-size:32px;')
                    anchor.appendChild(doc.createTextNode(tok))
                    nodes.append(anchor)

                elif tok==self.OBJ_REP:
                    src = images[ img_index ]
                    if src in skip_imgs:
                        img_index += 1
                        continue
                    img = doc.createElement('img')
                    if not src.startswith('/tmp'):
                        q = QImage(src)
                        a,b = os.path.split(src)
                        tmp = '/tmp/%s.png'%b
                        if tmp not in self.qimages:
                            qlab = QLabel()
                            qs = q.scaled(256,256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            qpix = QPixmap.fromImage(qs)
                            qlab.setPixmap(qpix)
                            self.images_layout.addWidget(qlab)
                            self.qimages[tmp]=qpix

                        qs = q.scaled(32,32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        qs.save(tmp)
                        src = tmp

                    img_index += 1
                    img.setAttribute('src', src)
                    anchor = doc.createElement('a')
                    anchor.setAttribute('href', src)
                    anchor.appendChild(img)
                    nodes.append(anchor)
                elif type(tok) is bytes:
                    assert tok==b'\n'
                    nodes.append( doc.createElement('br') )
                elif type(tok) is str:
                    if tok in self.SYNTAX:
                        f = doc.createElement('font')
                        f.setAttribute('color', self.SYNTAX[tok])
                        f.appendChild(doc.createTextNode(tok))
                        nodes.append(f)
                    else:
                        nodes.append(doc.createTextNode(tok))
                elif type(tok) in (list,tuple):
                    nodes.append(doc.createTextNode(''.join(tok)))

            for elt in nodes:
                p.appendChild(elt)

            html = p.toxml()
            html = html.replace('<br />', '<br/>')
            o = []
            lines = []
            for idx, ln in enumerate(html.split('<br/>')):
                if '{' in ln and ln.count('{')==ln.count('}') and ln.index('{') < ln.index('}'):
                    ln = ln.replace('{', '{<u style="background-color:blue">')
                    ln = ln.replace('}', '</u>}')
                o.append(ln)
                lines.append(str(idx+1))

            ## TODO: this is just a quick fix, this should be synced with the scroll bar of the text widget
            if len(lines) <= 32:
                self.line_counts.setText( "<p style='line-height: 1.1;'>%s</p>" % '<br/>'.join(lines))
            else:
                lines = lines[:32] + ['...', str(len(lines))]
                self.line_counts.setText( "<p style='line-height: 1.1;'>%s</p>" % '<br/>'.join(lines))
            html = '<br/>'.join(o)

            html = html.replace('[', '[<b style="background-color:purple">')
            html = html.replace(']', '</b>]')

            if html.count('(')==html.count(')'):
                html = html.replace('(', '<i style="background-color:gray; color:black">(')
                html = html.replace(')', ')</i>')

            if self.on_syntax_highlight_post:
                html = self.on_syntax_highlight_post(html)

            self.editor.setHtml(html)
            self.prev_html = self.editor.toHtml()
            cur = self.editor.textCursor()
            cur.setPosition(pos)
            self.editor.setTextCursor(cur)

    def get_blend_symbol(self, url):
        if url not in self.blend_syms:
            self.blend_syms[url] = self.blender_symbols.pop()
        return self.blend_syms[url]

    def on_new_blend(self, url, document=None, cursor=None):
        print('got blender file:', url)
        #cursor.insertHtml('<a href="BLENDER:%s" style="color:blue">%s</a>' % (len(self.blends), self.OBJ_BLEND))
        sym = self.get_blend_symbol(url)
        if cursor is None:
            cursor = self.editor.textCursor()

        cursor.insertHtml('<a href="BLENDER:%s" style="color:blue">%s</a>' % (len(self.blends), sym))

        info = self.parse_blend(url)
        info['URL'] = url
        info['SYMBOL'] = sym
        self.blends.append(info)
        self.blend_files[url] = info
        if 'THUMB' in info and info['THUMB']:
            self.blend_thumbs[sym] = info['THUMB']
            q = QImage(info['THUMB'])
            qpix = QPixmap.fromImage(q) #.scaled(64,64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.blend_previews[url] = qpix

        clear_layout(self.images_layout)
        self.images_layout.addWidget(self.blend_to_qt(info))

    def get_blend_from_symbol(self, sym):
        for info in self.blends:
            if info['SYMBOL'] == sym:
                return info

    def run_script(self, *args):
        txt = self.editor.toPlainText()
        header = [
            'import bpy',
        ]
        py = []
        blends = []
        for c in txt:  ## note: not using .splitlines because it removes OBJ_REP?
            if c in self.BLEND_SYMS:
                info = self.get_blend_from_symbol(c)
                sel = info['selected']
                blends.append(info)
                if len(blends)==1:
                    if len(sel) == 0:
                        py.append('(bpy.data.objects)')
                    elif len(sel) == 1:
                        py.append('(bpy.data.objects["%s"])' % sel[0])
                    else:
                        names = ['"%s"' % n for n in sel]
                        py.append('[bpy.data.objects[n] for n in (%s)]' % ','.join(names))
                else:  ## extra blends must be linked in
                    header += [
                    'with bpy.data.libraries.load("%s") as (data_from, data_to):' % info['URL'],
                    '   data_to.objects=data_from.objects',
                    ]
                    if len(sel)==0:
                        header += [
                        'for ob in data_to.objects:',
                        '   if ob is not None: bpy.data.scenes[0].collection.objects.link(ob)',
                        ]
                    elif len(sel)==1:
                        header += [
                        '__blend__%s=[]' % len(blends),
                        'for ob in data_to.objects:',
                        '   if ob is not None and ob.name =="%s":' % sel[0],
                        '       bpy.data.scenes[0].collection.objects.link(ob)',
                        '       __blend__%s = ob' % len(blends),
                        ]
                        py.append('(__blend__%s)' % len(blends))

                    else:
                        names = ['"%s"' % n for n in sel]
                        header += [
                        '__blend__%s=[]' % len(blends),
                        'for ob in data_to.objects:',
                        '   if ob is not None and ob.name in (%s):' % ','.join(names),
                        '       bpy.data.scenes[0].collection.objects.link(ob)',
                        '       __blend__%s.append(ob)' % len(blends),
                        ]
                        py.append('(__blend__%s)' % len(blends))

                continue
            if c == self.OBJ_REP:
                ## TODO images
                continue
            py.append(c)
        py = '\n'.join(header) + '\n' + ''.join(py)
        print(py)
        self.show_script(py)
        if sys.platform=='win32':
            tmp='C:\\tmp\\__user__.py'
        else:
            tmp='/tmp/__user__.py'
        open(tmp,'wb').write(py.encode('utf-8'))
        cmd = [BLENDER]
        if blends:
            cmd.append(blends[0]['URL'] )
        cmd += ['--window-geometry','640','100', '800','800', '--python-exit-code','1', '--python', tmp ]
        print(cmd)
        subprocess.check_call(cmd)

    def show_script(self, txt):
        clear_layout(self.images_layout)
        lab = QLabel(txt)
        lab.setStyleSheet('font-size:8px')
        self.images_layout.addWidget(lab)


    def open_blend(self, url):
        cmd = [BLENDER, url]
        print(cmd)
        subprocess.check_call(cmd)

    def blend_to_qt(self, dump):
        layout = QVBoxLayout()
        container = QWidget()
        container.setLayout(layout)
        url = dump['URL']

        qsym = QLabel(self.blend_syms[url])
        qsym.setStyleSheet('font-size:64px; color:cyan;')
        layout.addWidget(qsym)

        a,b = os.path.split(url)
        btn = QPushButton('open: '+b)
        btn.setStyleSheet('background-color:gray; color:white')
        btn.clicked.connect(lambda : self.open_blend(url))
        layout.addWidget(btn)

        if url not in self.blend_previews:
            cmd = [BLENDER, url, '--background', '--python', __file__, '--', '--render=/tmp/__blend__.png']
            print(cmd)
            subprocess.check_call(cmd)
            q = QImage('/tmp/__blend__.png')
            qpix = QPixmap.fromImage(q)
            self.blend_previews[url]=qpix

        qlab = QLabel()
        qlab.setPixmap(self.blend_previews[url])
        layout.addWidget(qlab)


        layout.addStretch(1)

        for name in dump['objects']:
            btn = QPushButton(name)
            btn.setCheckable(True)
            if name in dump['selected']:
                btn.setChecked(True)
            btn.toggled.connect(
                lambda x,n=name: self.toggle_blend_object(x,n, dump)
            )
            layout.addWidget(btn)

        return container

    def toggle_blend_object(self, toggle, name, info):
        if toggle:
            if name not in info['selected']:
                info['selected'].append(name)
        else:
            if name in info['selected']:
                info['selected'].remove(name)

    def parse_blend(self, blend):
        cmd = [BLENDER, blend, '--background', '--python', __file__, '--', '--dump-blend=/tmp/__blend__.json']
        print(cmd)
        subprocess.check_call(cmd)
        info = json.loads(open('/tmp/__blend__.json').read())
        print(info)

        buf,x,y = nailer.blend_extract_thumb(blend)
        if buf:
            png = nailer.write_png(buf,x,y)
            a,b = os.path.split(blend)
            tmp = '/tmp/%s.thumb.png' % b
            open(tmp,'wb').write(png)
            info['THUMB']=tmp
            print(tmp)

        return info

    def on_link_clicked(self, url, evt):
        print('clicked:', url)
        if url.isdigit():
            index = int(url)
            print('clicked on table:', index)
            tab = self.table_to_qt(self.tables[index])
            clear_layout(self.images_layout)
            self.images_layout.addWidget(tab)
            tab.show()
        elif url.startswith("BLENDER:"):
            info = self.blends[ int(url.split(':')[-1] ) ]
            url = info['URL']
            clear_layout(self.images_layout)
            self.images_layout.addWidget(self.blend_to_qt(info))

        elif url in self.on_sym_clicked:
            self.on_sym_clicked[url](url)

        elif url in self.qimages:
            qlab = QLabel()
            qlab.setPixmap(self.qimages[url])
            clear_layout(self.images_layout)
            self.images_layout.addWidget(qlab)
            qlab.show()

    def table_to_qt(self, elt):
        tab = QTableWidget()
        tab.setStyleSheet('background-color:white; color:black;')
        rows = elt.getElementsByTagName('tr')
        tab.setRowCount(len(rows))
        tab.setColumnCount( len(rows[0].getElementsByTagName('td')) )
        for y, tr in enumerate( elt.getElementsByTagName('tr') ):
            for x, td in enumerate( tr.getElementsByTagName('td') ):
                txt = get_dom_text(td.childNodes).strip()
                print(x,y, txt)
                tab.setItem(y,x, QTableWidgetItem(txt))

        tab.resizeColumnsToContents()
        return tab

    def on_new_table(self, elt):
        tab = self.table_to_qt(elt)
        clear_layout(self.images_layout)
        self.images_layout.addStretch(1)
        self.images_layout.addWidget(tab)
        return elt

    def on_mouse_over_anchor(self, event, url, sym):
        if sym==self.OBJ_TABLE:
            assert url.isdigit()
            tab = self.tables[int(url)]
            arr = self.table_to_code(tab)
            print(arr)
            QToolTip.showText(event.globalPosition().toPoint(), arr)
        elif sym in self.BLEND_SYMS:
            info = self.blends[ int(url.split(':')[-1]) ]
            tip = info['URL'] + '\nselected:\n'
            if len(info['selected']):
                for name in info['selected']:
                    tip += '\t'+name + '\n'
            else:
                tip = ' (no objects selected)'
            QToolTip.showText(event.globalPosition().toPoint(), tip)

    def table_to_code(self, elt):
        o = []
        rows = elt.getElementsByTagName('tr')
        if len(rows)==1:
            tr = rows[0]
            for x, td in enumerate( tr.getElementsByTagName('td') ):
                txt = get_dom_text(td.childNodes).strip()
                o.append(txt)
        else:
            for y, tr in enumerate( rows ):
                r = []
                for x, td in enumerate( tr.getElementsByTagName('td') ):
                    txt = get_dom_text(td.childNodes).strip()
                    if not txt:
                        r.append('0')
                    else:
                        r.append(txt)
                o.append('{%s}' % ','.join(r))

        return '{%s}' % ','.join(o)


def get_dom_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
        else:
            rc.append(get_dom_text(node.childNodes))
    return ''.join(rc)

def clear_layout(layout):
    for i in reversed(range(layout.count())):
        widget = layout.itemAt(i).widget()
        if widget is not None: widget.setParent(None)

if __name__ == "__main__":
    print('num args:', len(sys.argv))
    print(sys.argv)
    app = QApplication(sys.argv)
    app.setApplicationName("Megasolid Idiom")
    window = MegasolidCodeEditor()
    window.reset()
    user_vars = list(string.ascii_letters)
    user_vars.reverse()
    for arg in sys.argv[1:]:
        if arg.endswith('.blend'):
            cur = window.editor.textCursor()
            cur.insertText('%s = ' % user_vars.pop())
            window.on_new_blend(arg)
            cur.insertText('\n')
        else:
            cur.insertText(arg + '\n')


    app.exec()
