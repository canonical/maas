# -*- coding: utf-8 -*-
from django.db import models
from south.db import db
from south.utils import datetime_utils as datetime
from south.v2 import DataMigration


adjectives = """\
abandoned able absolute academic acceptable acclaimed accomplished
accurate aching acidic acrobatic active actual adept admirable admired
adolescent adorable adored advanced adventurous affectionate afraid aged
aggravating aggressive agile agitated agonizing agreeable ajar alarmed
alarming alert alienated alive all altruistic amazing ambitious ample
amused amusing anchored ancient angelic angry anguished animated annual
another antique anxious any apprehensive appropriate apt arctic arid
aromatic artistic ashamed assured astonishing athletic attached
attentive attractive austere authentic authorized automatic avaricious
average aware awesome awful awkward babyish back bad baggy bare barren
basic beautiful belated beloved beneficial best better bewitched big
biodegradable bitesize bitter black bland blank blaring bleak blind
blissful blond blue blushing bogus boiling bold bony boring bossy both
bouncy bountiful bowed brave breakable brief bright brilliant brisk
broken bronze brown bruised bubbly bulky bumpy buoyant burdensome burly
bustling busy buttery buzzing calculating calm candid canine capital
carefree careful careless caring cautious cavernous celebrated charming
cheap cheerful cheery chief chilly chubby circular classic clean clear
clever close closed cloudy clueless clumsy cluttered coarse cold
colorful colorless colossal comfortable common compassionate competent
complete complex complicated composed concerned concrete confused
conscious considerate constant content conventional cooked cool
cooperative coordinated corny corrupt costly courageous courteous crafty
crazy creamy creative creepy criminal crisp critical crooked crowded
cruel crushing cuddly cultivated cultured cumbersome curly curvy cute
cylindrical damaged damp dangerous dapper daring dark darling dazzling
dead deadly deafening dear dearest decent decimal decisive deep
defenseless defensive defiant deficient definite definitive delayed
delectable delicious delightful delirious demanding dense dental
dependable dependent descriptive deserted detailed determined devoted
different difficult digital diligent dim dimpled dimwitted direct dirty
disastrous discrete disfigured disguised disgusting dishonest disloyal
dismal distant distinct distorted dizzy dopey doting double downright
drab drafty dramatic dreary droopy dry dual dull dutiful each eager
early earnest easy easygoing ecstatic edible educated elaborate elastic
elated elderly electric elegant elementary elliptical embarrassed
embellished eminent emotional empty enchanted enchanting energetic
enlightened enormous enraged entire envious equal equatorial essential
esteemed ethical euphoric even evergreen everlasting every evil exalted
excellent excitable excited exciting exemplary exhausted exotic
expensive experienced expert extraneous extroverted fabulous failing
faint fair faithful fake false familiar famous fancy fantastic far
faraway fast fat fatal fatherly favorable favorite fearful fearless
feisty feline female feminine few fickle filthy fine finished firm first
firsthand fitting fixed flaky flamboyant flashy flat flawed flawless
flickering flimsy flippant flowery fluffy fluid flustered focused fond
foolhardy foolish forceful forked formal forsaken forthright fortunate
fragrant frail frank frayed free french frequent fresh friendly
frightened frightening frigid frilly frivolous frizzy front frosty
frozen frugal fruitful full fumbling functional funny fussy fuzzy
gargantuan gaseous general generous gentle genuine giant giddy gifted
gigantic giving glamorous glaring glass gleaming gleeful glistening
glittering gloomy glorious glossy glum golden good gorgeous graceful
gracious grand grandiose granular grateful grave gray great greedy green
gregarious grim grimy gripping grizzled gross grotesque grouchy grounded
growing growling grown grubby gruesome grumpy guilty gullible gummy
hairy half handmade handsome handy happy hard harmful harmless
harmonious harsh hasty hateful haunting healthy heartfelt hearty
heavenly heavy hefty helpful helpless hidden hideous high hilarious
hoarse hollow homely honest honorable honored hopeful horrible
hospitable hot huge humble humiliating humming humongous hungry hurtful
husky icky icy ideal idealistic identical idiotic idle idolized ignorant
ill illegal illiterate illustrious imaginary imaginative immaculate
immaterial immediate immense impartial impassioned impeccable imperfect
imperturbable impish impolite important impossible impractical
impressionable impressive improbable impure inborn incomparable
incompatible incomplete inconsequential incredible indelible indolent
inexperienced infamous infantile infatuated inferior infinite informal
innocent insecure insidious insignificant insistent instructive
insubstantial intelligent intent intentional interesting internal
international intrepid ironclad irresponsible irritating itchy jaded
jagged jaunty jealous jittery joint jolly jovial joyful joyous jubilant
judicious juicy jumbo jumpy junior juvenile kaleidoscopic keen key kind
kindhearted kindly klutzy knobby knotty knowing knowledgeable known
kooky kosher lame lanky large last lasting late lavish lawful lazy
leading leafy lean left legal legitimate light lighthearted likable
likely limited limp limping linear lined liquid little live lively livid
loathsome lone lonely long loose lopsided lost loud lovable lovely
loving low loyal lucky lumbering luminous lumpy lustrous luxurious mad
magnificent majestic major male mammoth married marvelous masculine
massive mature meager mealy mean measly meaty medical mediocre medium
meek mellow melodic memorable menacing merry messy metallic mild milky
mindless miniature minor minty miserable miserly misguided misty mixed
modern modest moist monstrous monthly monumental moral mortified
motherly motionless mountainous muddy muffled multicolored mundane murky
mushy musty muted mysterious naive narrow nasty natural naughty nautical
near neat necessary needy negative neglected negligible neighboring
nervous new next nice nifty nimble nippy nocturnal noisy nonstop normal
notable noted noteworthy novel noxious numb nutritious nutty obedient
obese oblong obvious occasional odd oddball offbeat offensive official
oily old overlooked only open optimal optimistic opulent orange orderly
ordinary organic original ornate ornery other our outgoing outlandish
outlying outrageous outstanding oval overcooked overdue overjoyed
palatable pale paltry parallel parched partial passionate past pastel
peaceful peppery perfect perfumed periodic perky personal pertinent
pesky pessimistic petty phony physical piercing pink pitiful plain
plaintive plastic playful pleasant pleased pleasing plump plush pointed
pointless poised polished polite political poor popular portly posh
positive possible potable powerful powerless practical precious present
prestigious pretty previous pricey prickly primary prime pristine
private prize probable productive profitable profuse proper proud
prudent punctual pungent puny pure purple pushy putrid puzzled puzzling
quaint qualified quarrelsome quarterly queasy querulous questionable
quick quiet quintessential quirky quixotic quizzical radiant ragged
rapid rare rash raw ready real realistic reasonable recent reckless
rectangular red reflecting regal regular reliable relieved remarkable
remorseful remote repentant repulsive required respectful responsible
revolving rewarding rich right rigid ringed ripe roasted robust rosy
rotating rotten rough round rowdy royal rubbery ruddy rude rundown runny
rural rusty sad safe salty same sandy sane sarcastic sardonic satisfied
scaly scarce scared scary scented scholarly scientific scornful scratchy
scrawny second secondary secret selfish sentimental separate serene
serious serpentine several severe shabby shadowy shady shallow shameful
shameless sharp shimmering shiny shocked shocking shoddy short showy
shrill shy sick silent silky silly silver similar simple simplistic
sinful single sizzling skeletal skinny sleepy slight slim slimy slippery
slow slushy small smart smoggy smooth smug snappy snarling sneaky
sniveling snoopy sociable soft soggy solid somber some sophisticated
sore sorrowful soulful soupy sour spanish sparkling sparse specific
spectacular speedy spherical spicy spiffy spirited spiteful splendid
spotless spotted spry square squeaky squiggly stable staid stained stale
standard starchy stark starry steel steep sticky stiff stimulating
stingy stormy straight strange strict strident striking striped strong
studious stunning stupendous stupid sturdy stylish subdued submissive
substantial subtle suburban sudden sugary sunny super superb superficial
superior supportive surprised suspicious svelte sweaty sweet sweltering
swift sympathetic talkative tall tame tan tangible tart tasty tattered
taut tedious teeming tempting tender tense tepid terrible terrific testy
thankful that these thick thin third thirsty this thorny thorough those
thoughtful threadbare thrifty thunderous tidy tight timely tinted tiny
tired torn total tough tragic trained traumatic treasured tremendous
triangular tricky trifling trim trivial troubled true trusting
trustworthy trusty truthful tubby turbulent twin ugly ultimate
unacceptable unaware uncomfortable uncommon unconscious understated
unequaled uneven unfinished unfit unfolded unfortunate unhappy unhealthy
uniform unimportant unique united unkempt unknown unlawful unlined
unlucky unnatural unpleasant unrealistic unripe unruly unselfish
unsightly unsteady unsung untidy untimely untried untrue unused unusual
unwelcome unwieldy unwilling unwitting unwritten upbeat upright upset
urban usable used useful useless utilized utter vacant vague vain valid
valuable vapid variable vast velvety venerated vengeful verifiable
vibrant vicious victorious vigilant vigorous villainous violent violet
virtual virtuous visible vital vivacious vivid voluminous wan warlike
warm warmhearted warped wary wasteful watchful waterlogged watery wavy
weak wealthy weary webbed wee weekly weepy weighty weird welcome wet
which whimsical whirlwind whispered white whole whopping wicked wide
wiggly wild willing wilted winding windy winged wiry wise witty wobbly
woeful wonderful wooden woozy wordy worldly worn worried worrisome worse
worst worthless worthwhile worthy wrathful wretched writhing wrong wry
yawning yearly yellow yellowish young youthful yummy zany zealous zesty
zigzag
"""

nouns = """\
account achiever acoustics act action activity actor addition adjustment
advertisement advice aftermath afternoon afterthought agreement air
airplane airport alarm alley amount amusement anger angle animal answer
ant ants apparatus apparel apple apples appliance approval arch argument
arithmetic arm army art attack attempt attention attraction aunt
authority babies baby back badge bag bait balance ball balloon balls
banana band base baseball basin basket basketball bat bath battle bead
beam bean bear bears beast bed bedroom beds bee beef beetle beggar
beginner behavior belief believe bell bells berry bike bikes bird birds
birth birthday bit bite blade blood blow board boat boats body bomb bone
book books boot border bottle boundary box boy boys brain brake branch
brass bread breakfast breath brick bridge brother brothers brush bubble
bucket building bulb bun burn burst bushes business butter button
cabbage cable cactus cake cakes calculator calendar camera camp can
cannon canvas cap caption car card care carpenter carriage cars cart
cast cat cats cattle cause cave celery cellar cemetery cent chain chair
chairs chalk chance change channel cheese cherries cherry chess chicken
chickens children chin church circle clam class clock clocks cloth cloud
clouds clover club coach coal coast coat cobweb coil collar color comb
comfort committee company comparison competition condition connection
control cook copper copy cord cork corn cough country cover cow cows
crack cracker crate crayon cream creator creature credit crib crime
crook crow crowd crown crush cry cub cup current curtain curve cushion
dad daughter day death debt decision deer degree design desire desk
destruction detail development digestion dime dinner dinosaurs direction
dirt discovery discussion disease disgust distance distribution division
dock doctor dog dogs doll dolls donkey door downtown drain drawer dress
drink driving drop drug drum duck ducks dust ear earth earthquake edge
education effect egg eggnog eggs elbow end engine error event example
exchange existence expansion experience expert eye eyes face fact
fairies fall family fan fang farm farmer father faucet fear feast
feather feeling feet fiction field fifth fight finger fire fireman fish
flag flame flavor flesh flight flock floor flower flowers fly fog fold
food foot force fork form fowl frame friction friend friends frog frogs
front fruit fuel furniture game garden gate geese ghost giants giraffe
girl girls glass glove glue goat gold goldfish goose government governor
grade grain grandfather grandmother grape grass grip ground group growth
guide guitar gun hair haircut hall hammer hand hands harbor harmony hat
hate head health hearing heart heat help hen hill history hobbies hole
holiday home honey hook hope horn horse horses hose hospital hot hour
house houses humor hydrant ice icicle idea impulse income increase
industry ink insect instrument insurance interest invention iron island
jail jam jar jeans jelly jellyfish jewel join joke journey judge juice
jump kettle key kick kiss kite kitten kittens kitty knee knife knot
knowledge laborer lace ladybug lake lamp land language laugh lawyer lead
leaf learning leather leg legs letter letters lettuce level library lift
light limit line linen lip liquid list lizards loaf lock locket look
loss love low lumber lunch lunchroom machine magic maid mailbox man
manager map marble mark market mask mass match meal measure meat meeting
memory men metal mice middle milk mind mine minister mint minute mist
mitten mom money monkey month moon morning mother motion mountain mouth
move muscle music nail name nation neck need needle nerve nest net news
night noise north nose note notebook number nut oatmeal observation
ocean offer office oil operation opinion orange oranges order
organization ornament oven owl owner page pail pain paint pan pancake
paper parcel parent park part partner party passenger paste patch
payment peace pear pen pencil person pest pet pets pickle picture pie
pies pig pigs pin pipe pizzas place plane planes plant plantation plants
plastic plate play playground pleasure plot plough pocket point poison
police polish pollution popcorn porter position pot potato powder power
price print prison process produce profit property prose protest pull
pump punishment purpose push quarter quartz queen question quicksand
quiet quill quilt quince quiver rabbit rabbits rail railway rain
rainstorm rake range rat rate ray reaction reading reason receipt recess
record regret relation religion representative request respect rest
reward rhythm rice riddle rifle ring rings river road robin rock rod
roll roof room root rose route rub rule run sack sail salt sand scale
scarecrow scarf scene scent school science scissors screw sea seashore
seat secretary seed selection self sense servant shade shake shame shape
sheep sheet shelf ship shirt shock shoe shoes shop show side sidewalk
sign silk silver sink sister sisters size skate skin skirt sky slave
sleep sleet slip slope smash smell smile smoke snail snails snake snakes
sneeze snow soap society sock soda sofa son song songs sort sound soup
space spade spark spiders sponge spoon spot spring spy square squirrel
stage stamp star start statement station steam steel stem step stew
stick sticks stitch stocking stomach stone stop store story stove
stranger straw stream street stretch string structure substance sugar
suggestion suit summer sun support surprise sweater swim swing system
table tail talk tank taste tax teaching team teeth temper tendency tent
territory test texture theory thing things thought thread thrill throat
throne thumb thunder ticket tiger time tin title toad toe toes tomatoes
tongue tooth toothbrush toothpaste top touch town toy toys trade trail
train trains tramp transport tray treatment tree trees trick trip
trouble trousers truck trucks tub turkey turn twig twist umbrella uncle
underwear unit use vacation value van vase vegetable veil vein verse
vessel vest view visitor voice volcano volleyball voyage walk wall war
wash waste watch water wave waves wax way wealth weather week weight
wheel whip whistle wilderness wind window wine wing winter wire wish
woman women wood wool word work worm wound wren wrench wrist writer
writing yak yam yard yarn year yoke zebra zephyr zinc zipper zoo
"""


class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        CandidateName = orm["maasserver.CandidateName"]
        CandidateName.objects.bulk_create((
            CandidateName(name=name, position=1)
            for name in adjectives.split()
        ))
        CandidateName.objects.bulk_create((
            CandidateName(name=name, position=2)
            for name in nouns.split()
        ))

    def backwards(self, orm):
        "Write your backwards methods here."
        CandidateName = orm["maasserver.CandidateName"]
        CandidateName.objects.filter(
            name__in=adjectives.split(), position=1).delete()
        CandidateName.objects.filter(
            name__in=nouns.split(), position=2).delete()

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': "orm['auth.Group']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': "orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'maasserver.bootimage': {
            'Meta': {'unique_together': "((u'nodegroup', u'osystem', u'architecture', u'subarchitecture', u'release', u'purpose', u'label'),)", 'object_name': 'BootImage'},
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'default': "u'release'", 'max_length': '255'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'osystem': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'purpose': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'release': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'subarchitecture': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'supported_subarches': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'xinstall_path': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'xinstall_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '30', 'null': 'True', 'blank': 'True'})
        },
        'maasserver.bootresource': {
            'Meta': {'unique_together': "((u'rtype', u'name', u'architecture'),)", 'object_name': 'BootResource'},
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'extra': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'rtype': ('django.db.models.fields.IntegerField', [], {'max_length': '10'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.bootresourcefile': {
            'Meta': {'unique_together': "((u'resource_set', u'filetype'),)", 'object_name': 'BootResourceFile'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'extra': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filetype': ('django.db.models.fields.CharField', [], {'default': "u'tgz'", 'max_length': '20'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'largefile': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.LargeFile']"}),
            'resource_set': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'files'", 'to': "orm['maasserver.BootResourceSet']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.bootresourceset': {
            'Meta': {'unique_together': "((u'resource', u'version'),)", 'object_name': 'BootResourceSet'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'resource': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'sets'", 'to': "orm['maasserver.BootResource']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'maasserver.bootsource': {
            'Meta': {'object_name': 'BootSource'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keyring_data': ('maasserver.fields.EditableBinaryField', [], {'blank': 'True'}),
            'keyring_filename': ('django.db.models.fields.FilePathField', [], {'max_length': '100', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'url': ('django.db.models.fields.URLField', [], {'unique': 'True', 'max_length': '200'})
        },
        'maasserver.bootsourceselection': {
            'Meta': {'object_name': 'BootSourceSelection'},
            'arches': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'boot_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.BootSource']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'labels': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'release': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'subarches': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.candidatename': {
            'Meta': {'unique_together': "((u'name', u'position'),)", 'object_name': 'CandidateName'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'position': ('django.db.models.fields.IntegerField', [], {})
        },
        'maasserver.componenterror': {
            'Meta': {'object_name': 'ComponentError'},
            'component': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'error': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.config': {
            'Meta': {'object_name': 'Config'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'value': ('maasserver.fields.JSONObjectField', [], {'null': 'True'})
        },
        'maasserver.dhcplease': {
            'Meta': {'object_name': 'DHCPLease'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'mac': ('maasserver.fields.MACAddressField', [], {}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"})
        },
        'maasserver.downloadprogress': {
            'Meta': {'object_name': 'DownloadProgress'},
            'bytes_downloaded': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'error': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'size': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.event': {
            'Meta': {'object_name': 'Event'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'default': "u''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']"}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.EventType']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.eventtype': {
            'Meta': {'object_name': 'EventType'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.filestorage': {
            'Meta': {'unique_together': "((u'filename', u'owner'),)", 'object_name': 'FileStorage'},
            'content': ('metadataserver.fields.BinaryField', [], {'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'default': "u'cf9a93a6-2465-11e4-b243-000c29a40c60'", 'unique': 'True', 'max_length': '36'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'maasserver.largefile': {
            'Meta': {'object_name': 'LargeFile'},
            'content': ('maasserver.fields.LargeObjectField', [], {}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sha256': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'total_size': ('django.db.models.fields.BigIntegerField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.licensekey': {
            'Meta': {'unique_together': "((u'osystem', u'distro_series'),)", 'object_name': 'LicenseKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license_key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'osystem': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.macaddress': {
            'Meta': {'ordering': "(u'created',)", 'object_name': 'MACAddress'},
            'cluster_interface': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['maasserver.NodeGroupInterface']", 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addresses': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.StaticIPAddress']", 'symmetrical': 'False', 'through': "orm['maasserver.MACStaticIPAddressLink']", 'blank': 'True'}),
            'mac_address': ('maasserver.fields.MACAddressField', [], {'unique': 'True'}),
            'networks': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.Network']", 'symmetrical': 'False', 'blank': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.macstaticipaddresslink': {
            'Meta': {'unique_together': "((u'ip_address', u'mac_address'),)", 'object_name': 'MACStaticIPAddressLink'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.StaticIPAddress']", 'unique': 'True'}),
            'mac_address': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.MACAddress']"}),
            'nic_alias': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.network': {
            'Meta': {'object_name': 'Network'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'netmask': ('maasserver.fields.MAASIPAddressField', [], {'max_length': '39'}),
            'vlan_tag': ('django.db.models.fields.PositiveSmallIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'})
        },
        'maasserver.node': {
            'Meta': {'object_name': 'Node'},
            'agent_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '31'}),
            'boot_type': ('django.db.models.fields.CharField', [], {'default': "u'fastpath'", 'max_length': '20'}),
            'cpu_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'error': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'error_description': ('django.db.models.fields.TextField', [], {'default': "u''", 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'unique': 'True', 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license_key': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'netboot': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']", 'null': 'True'}),
            'osystem': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'power_parameters': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'power_state': ('django.db.models.fields.CharField', [], {'default': "u'unknown'", 'max_length': '10'}),
            'power_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10', 'blank': 'True'}),
            'routers': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'macaddr'", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '10'}),
            'storage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'system_id': ('django.db.models.fields.CharField', [], {'default': "u'node-cf9c63fc-2465-11e4-b243-000c29a40c60'", 'unique': 'True', 'max_length': '41'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.Tag']", 'symmetrical': 'False'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'zone': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Zone']", 'on_delete': 'models.SET_DEFAULT'})
        },
        'maasserver.nodegroup': {
            'Meta': {'object_name': 'NodeGroup'},
            'api_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'api_token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'unique': 'True'}),
            'cluster_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'dhcp_key': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maas_url': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'})
        },
        'maasserver.nodegroupinterface': {
            'Meta': {'unique_together': "((u'nodegroup', u'name'),)", 'object_name': 'NodeGroupInterface'},
            'broadcast_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'foreign_dhcp_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interface': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'max_length': '39'}),
            'ip_range_high': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'ip_range_low': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'management': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'router_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'static_ip_range_high': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'static_ip_range_low': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'subnet_mask': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.sshkey': {
            'Meta': {'unique_together': "((u'user', u'key'),)", 'object_name': 'SSHKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.TextField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'maasserver.sslkey': {
            'Meta': {'unique_together': "((u'user', u'key'),)", 'object_name': 'SSLKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.TextField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'maasserver.staticipaddress': {
            'Meta': {'object_name': 'StaticIPAddress'},
            'alloc_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'maasserver.tag': {
            'Meta': {'object_name': 'Tag'},
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'definition': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kernel_opts': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        },
        'maasserver.zone': {
            'Meta': {'ordering': "[u'name']", 'object_name': 'Zone'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'piston.consumer': {
            'Meta': {'object_name': 'Consumer'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'pending'", 'max_length': '16'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'consumers'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'piston.token': {
            'Meta': {'object_name': 'Token'},
            'callback': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'callback_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'consumer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Consumer']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_approved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1408098041L'}),
            'token_type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': "orm['auth.User']"}),
            'verifier': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['maasserver']
    symmetrical = True
